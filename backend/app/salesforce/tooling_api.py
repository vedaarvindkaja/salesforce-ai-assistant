"""Salesforce Tooling API client.

Wraps SalesforceHTTPClient with Tooling-specific URLs and typed response
parsing. Holds the same SalesforceHTTPClient instance that RestAPIClient
uses — they share connection pool, token state, and refresh-on-401 logic
(see ADR-003).

Phase 1 scope: the 6 metadata types defined in app/models/tooling.py.
Phase 2 may add PermissionSet, WorkflowRule, ApprovalProcess, etc.

The Tooling API endpoint is /services/data/v60.0/tooling/query (note the
'tooling' segment between data and query). Otherwise the SOQL grammar and
response envelope match the REST API exactly — which is why we can share
the HTTP client between them.

Reference: https://developer.salesforce.com/docs/atlas.en-us.api_tooling.meta/api_tooling/intro_api_tooling.htm
"""

import asyncio
from typing import Optional

from app.models.tooling import (
    ApexClass,
    ApexTrigger,
    CustomField,
    EntityDefinition,
    FlowDefinition,
    ToolingQueryResponse,
    ValidationRule,
)
from app.salesforce.http_client import SalesforceHTTPClient


# ============================================================
# Tooling API base path — shared across all queries
# ============================================================

_TOOLING_QUERY_PATH = "/services/data/v60.0/tooling/query"


class ToolingAPIClient:
    """High-level Salesforce Tooling API client.

    Usage:
        http = SalesforceHTTPClient()
        async with http:
            await http.authenticate()
            tooling = ToolingAPIClient(http=http)
            classes = await tooling.query_apex_classes()

    Or share the HTTP client with a RestAPIClient:
        http = SalesforceHTTPClient()
        async with http:
            await http.authenticate()
            rest = RestAPIClient(http=http)
            tooling = ToolingAPIClient(http=http)
            # Both clients share the same auth state — refresh in one
            # is visible to the other immediately.

    Note: unlike RestAPIClient, this class does NOT implement __aenter__
    or authenticate(). It's intentionally a thin wrapper over an
    already-authenticated HTTP client. The owner of the HTTP client
    (typically the FastAPI lifespan) is responsible for lifecycle.
    """

    def __init__(self, http: SalesforceHTTPClient):
        """Construct a Tooling client around an existing HTTP client.

        Args:
            http: A SalesforceHTTPClient that has already had
                  authenticate() called. The Tooling client never
                  authenticates on its own; it borrows the HTTP client's
                  token state.
        """
        self._http = http

    # ----- generic SOQL — useful for ad-hoc Tooling queries -----

    async def query_raw(self, soql: str) -> dict:
        """Run an arbitrary SOQL query against the Tooling API.

        Returns raw dict. Useful for queries that don't map to one of the
        6 typed methods below (e.g., Week 5 Day 3+ exploration, Week 7
        Apex parser custom queries).

        Most callers should prefer the typed query_* methods which give
        Pydantic models back instead of dicts.
        """
        response = await self._http.request(
            "GET",
            _TOOLING_QUERY_PATH,
            params={"q": soql},
        )
        response.raise_for_status()
        return response.json()

    # ----- typed queries: one per metadata type -----

    async def query_apex_classes(
        self,
        *,
        include_body: bool = False,
        where: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> ToolingQueryResponse[ApexClass]:
        """Query ApexClass records.

        Args:
            include_body: If True, includes the Body field (source code).
                          Adds 5-50KB per class to the response; default
                          False keeps responses light.
            where: Optional WHERE clause (without the WHERE keyword).
                   Example: where="NamespacePrefix = null" for org-local
                   classes only.
            limit: Optional LIMIT clause value.

        Note on Body=None vs Body='(hidden)':
            For managed-package classes Salesforce returns the literal
            string "(hidden)" — that's NOT a missing value, it's
            Salesforce's way of saying "this exists but we won't show you
            the source." The Pydantic model preserves this distinction.
        """
        fields = [
            "Id", "Name", "ApiVersion", "Status", "IsValid",
            "LengthWithoutComments", "NamespacePrefix",
            "CreatedDate", "LastModifiedDate",
        ]
        if include_body:
            fields.append("Body")

        soql = self._build_soql("ApexClass", fields, where=where, limit=limit)
        return await self._typed_query(soql, ApexClass)

    async def query_apex_triggers(
        self,
        *,
        include_body: bool = False,
        where: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> ToolingQueryResponse[ApexTrigger]:
        """Query ApexTrigger records.

        See query_apex_classes for include_body semantics.
        """
        fields = [
            "Id", "Name", "TableEnumOrId", "ApiVersion", "Status", "IsValid",
            "UsageBeforeInsert", "UsageAfterInsert",
            "UsageBeforeUpdate", "UsageAfterUpdate",
            "UsageBeforeDelete", "UsageAfterDelete", "UsageAfterUndelete",
            "LengthWithoutComments", "NamespacePrefix",
            "CreatedDate", "LastModifiedDate",
        ]
        if include_body:
            fields.append("Body")

        soql = self._build_soql("ApexTrigger", fields, where=where, limit=limit)
        return await self._typed_query(soql, ApexTrigger)

    async def query_entity_definitions(
        self,
        *,
        where: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> ToolingQueryResponse[EntityDefinition]:
        """Query EntityDefinition records (unified standard + custom objects).

        Common use cases:
            - All customizable objects: where="IsCustomizable = true"
            - All custom objects: where="QualifiedApiName LIKE '%__c'"
            - Specific object: where="QualifiedApiName = 'Account'"
        """
        fields = [
            "DurableId", "QualifiedApiName", "Label",
            "IsCustomizable", "IsCustomSetting",
            "IsApexTriggerable", "IsWorkflowEnabled",
            "KeyPrefix", "NamespacePrefix",
        ]
        soql = self._build_soql("EntityDefinition", fields, where=where, limit=limit)
        return await self._typed_query(soql, EntityDefinition)

    async def query_custom_fields(
        self,
        *,
        where: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> ToolingQueryResponse[CustomField]:
        """Query CustomField records.

        Standard fields (Account.Name, etc.) are NOT here — they live in
        FieldDefinition. This method only returns custom fields. Phase 2
        may add a query_field_definitions() for full coverage.

        Common use case:
            - All custom fields on a specific object:
              where="TableEnumOrId = 'Account'"
        """
        fields = [
            "Id", "DeveloperName", "TableEnumOrId", "NamespacePrefix",
            "CreatedDate", "LastModifiedDate",
        ]
        soql = self._build_soql("CustomField", fields, where=where, limit=limit)
        return await self._typed_query(soql, CustomField)

    async def query_validation_rules(
        self,
        *,
        where: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> ToolingQueryResponse[ValidationRule]:
        """Query ValidationRule records (without Metadata expansion).

        Note: ErrorConditionFormula and ErrorDisplayField live under the
        Metadata sub-object, which requires a different query shape. Day 3
        will add a separate query_validation_rule_with_metadata(rule_id)
        method when the parser needs formula contents.
        """
        fields = [
            "Id", "ValidationName", "EntityDefinitionId",
            "Active", "Description", "ErrorMessage",
            "CreatedDate", "LastModifiedDate",
        ]
        soql = self._build_soql("ValidationRule", fields, where=where, limit=limit)
        return await self._typed_query(soql, ValidationRule)

    async def query_flow_definitions(
        self,
        *,
        where: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> ToolingQueryResponse[FlowDefinition]:
        """Query FlowDefinition records.

        FlowDefinition is the project wrapper; each version is a separate
        Flow record. To fetch the XML for the active version, use
        ActiveVersionId in a follow-up query (Week 7 territory).
        """
        fields = [
            "Id", "DeveloperName", "MasterLabel",
            "ActiveVersionId", "LatestVersionId",
            "NamespacePrefix", "CreatedDate", "LastModifiedDate",
        ]
        soql = self._build_soql("FlowDefinition", fields, where=where, limit=limit)
        return await self._typed_query(soql, FlowDefinition)

    # ----- convenience: run many typed queries concurrently -----

    async def extract_all_for_graph(
        self,
        *,
        include_apex_bodies: bool = False,
    ) -> dict:
        """Run all 6 typed queries concurrently and return a dict of results.

        Convenience method for Week 5 Day 5-6's "extract everything for
        the graph" workflow. Returns a dict keyed by metadata type:

            {
                "apex_classes": ToolingQueryResponse[ApexClass],
                "apex_triggers": ToolingQueryResponse[ApexTrigger],
                "entity_definitions": ToolingQueryResponse[EntityDefinition],
                "custom_fields": ToolingQueryResponse[CustomField],
                "validation_rules": ToolingQueryResponse[ValidationRule],
                "flow_definitions": ToolingQueryResponse[FlowDefinition],
            }

        Six queries fire in parallel via asyncio.gather. Real-org wall
        time should be ~1-2 seconds total instead of ~6 seconds sequential.

        Note: if any single query fails, the whole gather fails. Phase 2
        may want partial-success semantics; Phase 1 fails loud and clear.
        """
        results = await asyncio.gather(
            self.query_apex_classes(include_body=include_apex_bodies),
            self.query_apex_triggers(include_body=include_apex_bodies),
            self.query_entity_definitions(where="IsCustomizable = true"),
            self.query_custom_fields(),
            self.query_validation_rules(),
            self.query_flow_definitions(),
        )
        return {
            "apex_classes": results[0],
            "apex_triggers": results[1],
            "entity_definitions": results[2],
            "custom_fields": results[3],
            "validation_rules": results[4],
            "flow_definitions": results[5],
        }

    # ----- internals -----

    def _build_soql(
        self,
        sobject: str,
        fields: list[str],
        *,
        where: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> str:
        """Build a SOQL string from components.

        Kept simple: no JOIN support, no ORDER BY, no GROUP BY. If you
        need those, write the SOQL by hand and use query_raw() instead.
        """
        soql = f"SELECT {', '.join(fields)} FROM {sobject}"
        if where:
            soql += f" WHERE {where}"
        if limit:
            soql += f" LIMIT {limit}"
        return soql

    async def _typed_query(
        self,
        soql: str,
        record_type: type,
    ) -> ToolingQueryResponse:
        """Run a SOQL query and parse into ToolingQueryResponse[record_type].

        We parameterize the response wrapper at runtime via
        ToolingQueryResponse[record_type]. Pydantic + Python's generics
        handle the typing magic — the returned object's .records list is
        properly typed as list[record_type].
        """
        response = await self._http.request(
            "GET",
            _TOOLING_QUERY_PATH,
            params={"q": soql},
        )
        response.raise_for_status()
        # Pydantic generics: ToolingQueryResponse[ApexClass] is a concrete
        # subclass of ToolingQueryResponse with records typed as list[ApexClass].
        wrapper_type = ToolingQueryResponse[record_type]
        return wrapper_type.model_validate_json(response.text)


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
#
# Apex can call its OWN org's Tooling API in two ways:
#
# 1) From within the same org (rare for this kind of work):
#    Use Schema.describeSObjects() and similar describe calls. Direct
#    Tooling API access from Apex requires Named Credentials pointing to
#    the same org, which is awkward.
#
# 2) From a different "tooling" org (devops org calling target orgs):
#    Use Named Credentials + HTTP callouts to /services/data/.../tooling/query.
#    This is the closer parallel to what we're building.
#
# Manual Apex equivalent for option 2:
#
#    public class ToolingApiClient {
#        private static final String TOOLING_PATH = '/services/data/v60.0/tooling/query';
#
#        public ApexClassToolingResponse queryApexClasses(
#                Boolean includeBody, String whereClause, Integer recordLimit) {
#            List<String> fields = new List<String>{
#                'Id', 'Name', 'ApiVersion', 'Status', 'IsValid',
#                'LengthWithoutComments', 'NamespacePrefix',
#                'CreatedDate', 'LastModifiedDate'
#            };
#            if (includeBody) fields.add('Body');
#
#            String soql = buildSoql('ApexClass', fields, whereClause, recordLimit);
#            HttpRequest req = new HttpRequest();
#            req.setEndpoint('callout:My_Tooling_NC' + TOOLING_PATH +
#                            '?q=' + EncodingUtil.urlEncode(soql, 'UTF-8'));
#            req.setMethod('GET');
#            HttpResponse res = new Http().send(req);
#            return (ApexClassToolingResponse) JSON.deserialize(
#                res.getBody(), ApexClassToolingResponse.class);
#        }
#
#        // ... query_apex_triggers, query_custom_fields, etc. ...
#        // Each requires its own typed response wrapper class because
#        // Apex generics can't express ToolingResponse<T>.
#
#        public List<Object> extractAllForGraph() {
#            // Apex has NO equivalent to asyncio.gather. You'd either:
#            //   (a) Run 6 callouts sequentially (slow)
#            //   (b) Use Continuation API for parallel callouts (complex,
#            //       only works from Visualforce/Lightning contexts)
#            //   (c) Queue 6 @future methods (fire-and-forget, not gather)
#            // None of these match Python's clean "wait for all 6" semantics.
#        }
#    }
#
# Concept mapping:
# - asyncio.gather(...)                    → Continuation API in VF/LWC
#                                             contexts only; otherwise serial
# - Optional[str] = None keyword args      → method overloading or builder
# - Generic[T] in response wrapper         → one wrapper per record type
# - response.raise_for_status()            → manual: if (res.getStatusCode()
#                                             >= 400) { throw ... }
# - * in def (keyword-only arguments)      → no equivalent; rely on named
#                                             parameters via overloads
# - Shared HTTPClient across API clients   → one Named Credential, multiple
#                                             callout classes (similar idea,
#                                             very different mechanics)
#
# The big productivity wins for Python here:
#
# 1. asyncio.gather for extract_all_for_graph — 6 queries in 1-2 seconds
#    vs Apex's 6 sequential callouts in 6-12 seconds. For Week 8 Claude
#    tool use this matters: Claude might need 3-4 metadata queries per
#    user question, and parallel beats serial by 3-4x latency reduction.
#
# 2. Generic[T] for the response wrapper — one class, six uses. Apex
#    needs six classes for the same thing.
#
# 3. Pydantic ignoring unknown fields by default — Salesforce can add
#    fields to ApexClass and our code keeps working. Apex's strict
#    JSON.deserialize would throw.
# ============================================================