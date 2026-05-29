"""Pydantic models for Salesforce Tooling API responses.

The Tooling API exposes ~100 sObjects; this file models the 6 we need for
Week 6's metadata graph (see Week 4 Day 2 strategic pivot in NOTES.md and
ROADMAP.md Section 4 Week 5).

Design choices (locked Week 5 Day 2, see commit history):

- **Lean models.** Each model captures only the fields Week 6's graph
  actually consumes. Pydantic ignores unknown fields by default, so
  Salesforce can return more fields than we model without breaking anything.
  Add fields incrementally when concrete use cases appear.

- **ApexClass.Body is Optional.** A class with Body=None means "metadata
  fetched, source not yet fetched." Lets one model serve both shapes
  ("list of classes" vs "this class with source").

- **Generic ToolingQueryResponse[T].** All Tooling API SOQL responses share
  the envelope shape (totalSize, done, records). Parameterizing by record
  type gives type safety without per-type response classes.

Reference: https://developer.salesforce.com/docs/atlas.en-us.api_tooling.meta/api_tooling/
"""

from datetime import datetime
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel


# ============================================================
# Generic response envelope
# ============================================================
#
# TypeVar + Generic[T] is Python's way of saying "this class is
# parameterized by another type." The caller writes:
#
#     ToolingQueryResponse[ApexClass]
#
# and Pydantic + the type checker know that .records is list[ApexClass].
# No equivalent in Apex — Apex generics are restricted to a few platform
# types (List, Map, Set) and you can't declare your own.

T = TypeVar("T", bound=BaseModel)


class ToolingAttributes(BaseModel):
    """Metadata Salesforce attaches to every Tooling API record."""

    type: str
    """Salesforce sObject API name (e.g., 'ApexClass', 'CustomField')."""

    url: str
    """Relative URL where this record can be fetched directly."""


class ToolingQueryResponse(BaseModel, Generic[T]):
    """Envelope for any SOQL query against the Tooling API.

    Salesforce paginates large result sets via nextRecordsUrl. For Phase 1
    we deliberately don't follow pagination — Week 5 mock orgs have <1000
    records per type, well under the default 2000 record limit. Phase 2
    will add pagination when real orgs hit the limit.
    """

    totalSize: int
    """Total record count matching the query (may exceed records returned
    if pagination kicked in)."""

    done: bool
    """True if this response contains all results. False if more pages exist
    at nextRecordsUrl."""

    records: list[T]
    """The actual records, typed by the generic parameter."""

    nextRecordsUrl: Optional[str] = None
    """Set when done=False. We log a warning if we ever see this in Phase 1."""


# ============================================================
# 1. ApexClass — Apex source code
# ============================================================

class ApexClass(BaseModel):
    """A Salesforce Apex class.

    Body is optional because we often query just the metadata (list of
    classes) without pulling source. Week 7's Apex parser is the primary
    consumer of Body; Week 6's graph cares mostly about Name + Status.
    """

    attributes: ToolingAttributes
    Id: str
    Name: str
    """Class name without the 'class' keyword (e.g., 'AccountTriggerHandler')."""

    ApiVersion: float
    """The API version the class is compiled against (e.g., 60.0)."""

    Status: str
    """'Active', 'Inactive', or 'Deleted'. Inactive classes don't compile or run."""

    IsValid: bool
    """False if the class currently has compile errors against the org."""

    LengthWithoutComments: int
    """Useful for graph weight calculations and 'large class' detection."""

    NamespacePrefix: Optional[str] = None
    """Set for managed-package classes; None for org-local classes."""

    Body: Optional[str] = None
    """Apex source code. None when not yet fetched. Can be '(hidden)' for
    managed-package classes — Salesforce returns the literal string."""

    CreatedDate: Optional[datetime] = None
    LastModifiedDate: Optional[datetime] = None


# ============================================================
# 2. ApexTrigger — Apex triggers
# ============================================================

class ApexTrigger(BaseModel):
    """A Salesforce Apex trigger.

    Triggers are conceptually ApexClass + a triggering sObject + event types.
    Modeled separately because the graph queries them differently ('what
    triggers fire on Account?' is a common question).
    """

    attributes: ToolingAttributes
    Id: str
    Name: str
    TableEnumOrId: str
    """The sObject the trigger fires on. Standard objects use API name
    ('Account'); custom objects use the Id of the CustomObject record."""

    ApiVersion: float
    Status: str
    """'Active', 'Inactive', or 'Deleted'."""

    IsValid: bool

    UsageBeforeInsert: bool
    UsageAfterInsert: bool
    UsageBeforeUpdate: bool
    UsageAfterUpdate: bool
    UsageBeforeDelete: bool
    UsageAfterDelete: bool
    UsageAfterUndelete: bool
    """Seven boolean flags covering every trigger event. The graph uses
    these to answer 'which triggers fire on Account update?'"""

    LengthWithoutComments: int

    NamespacePrefix: Optional[str] = None
    Body: Optional[str] = None
    CreatedDate: Optional[datetime] = None
    LastModifiedDate: Optional[datetime] = None


# ============================================================
# 3. EntityDefinition — unified standard + custom objects
# ============================================================

class EntityDefinition(BaseModel):
    """A Salesforce sObject — standard (Account) or custom (My_Object__c).

    The Tooling API exposes this view that unifies both, which is gold:
    one query covers Account, Contact, AND MyCustom__c. Without
    EntityDefinition you'd need separate paths for standard vs custom
    objects.
    """

    attributes: ToolingAttributes
    DurableId: str
    """A stable identifier that works for both standard and custom objects.
    Use this as the graph node key, not Id."""

    QualifiedApiName: str
    """The API name you'd use in SOQL (e.g., 'Account', 'Custom__c')."""

    Label: str
    """Human-readable label (e.g., 'Account', 'Custom Object')."""

    IsCustomizable: bool
    """True if the object accepts custom fields, validation rules, etc."""

    IsCustomSetting: bool
    IsApexTriggerable: bool
    IsWorkflowEnabled: bool
    """Capability flags useful for graph filtering."""

    KeyPrefix: Optional[str] = None
    """The 3-character ID prefix (e.g., '001' for Account). None for some
    metadata-only objects."""

    NamespacePrefix: Optional[str] = None


# ============================================================
# 4. CustomField — field definitions
# ============================================================

class CustomField(BaseModel):
    """A custom field on any sObject.

    Standard fields (Account.Name, etc.) are NOT in this table — they're in
    FieldDefinition. For Phase 1 graph we focus on CustomField because
    'what depends on this CUSTOM field?' is the most common question.

    Phase 2 may expand to FieldDefinition for full coverage.
    """

    attributes: ToolingAttributes
    Id: str
    DeveloperName: str
    """The field's API name WITHOUT the __c suffix (e.g., 'Priority' for
    Priority__c). Add __c when constructing fully-qualified names."""

    TableEnumOrId: str
    """The sObject this field belongs to. Standard objects: API name
    ('Account'); custom objects: CustomObject Id. Same pattern as
    ApexTrigger.TableEnumOrId — annoying but consistent."""

    NamespacePrefix: Optional[str] = None
    CreatedDate: Optional[datetime] = None
    LastModifiedDate: Optional[datetime] = None


# ============================================================
# 5. ValidationRule — declarative validation
# ============================================================

class ValidationRule(BaseModel):
    """A validation rule on a sObject.

    Validation rules reference fields in their ErrorConditionFormula,
    which is the main reason they're in the graph. Week 7's parser will
    extract field references from the formula string.
    """

    attributes: ToolingAttributes
    Id: str
    ValidationName: str
    """The rule's developer name (e.g., 'Amount_Must_Be_Positive')."""

    EntityDefinitionId: str
    """The DurableId of the sObject this rule lives on. Maps cleanly to
    EntityDefinition.DurableId for graph edges."""

    Active: bool
    Description: Optional[str] = None
    ErrorMessage: Optional[str] = None

    # Note: ErrorConditionFormula and ErrorDisplayField require a Metadata
    # field expansion in the SOQL query — they live on ValidationRule's
    # Metadata sub-object, not as top-level fields. Week 5 Day 3 will
    # decide whether to flatten them here or use a separate model for the
    # expanded form. Parked as a Day 3 design question.

    CreatedDate: Optional[datetime] = None
    LastModifiedDate: Optional[datetime] = None


# ============================================================
# 6. FlowDefinition — Salesforce Flows
# ============================================================

class FlowDefinition(BaseModel):
    """A Flow definition (the metadata wrapper, not the Flow XML itself).

    Flows are versioned: FlowDefinition is the 'project' and each version
    is a separate Flow record. For Phase 1 we model the definition; Week 7
    will fetch the active version's XML when the parser needs it.
    """

    attributes: ToolingAttributes
    Id: str
    DeveloperName: str
    """Internal name (e.g., 'Update_Account_Owner')."""

    MasterLabel: Optional[str] = None
    """Human-readable label shown in Setup. Verified Week 5 Day 2 against
    a real dev org: MasterLabel via Tooling API SOQL on FlowDefinition is
    UNRELIABLE — all 5 FlowDefinitions in the test org returned null
    MasterLabel despite having meaningful labels in the Setup UI and
    being active flows.

    Likely cause: the user-facing label lives on the Flow record (the
    version), not on the FlowDefinition (the wrapper). Salesforce exposes
    `MasterLabel` on FlowDefinition in the schema but doesn't reliably
    populate it via this query path.

    For Week 6's graph: use DeveloperName as the display label, OR fetch
    the Flow record at ActiveVersionId and pull its label from there.
    Decision parked for Week 6 Day 1."""

    ActiveVersionId: Optional[str] = None
    """The Flow record Id of the currently active version. None if no version
    is active (Flow is in draft / deactivated)."""

    LatestVersionId: Optional[str] = None
    """Most recent version, active or not. Useful for 'what's the latest
    state of this flow' regardless of activation."""

    NamespacePrefix: Optional[str] = None
    CreatedDate: Optional[datetime] = None
    LastModifiedDate: Optional[datetime] = None


# ============================================================
# APEX EQUIVALENT (for comparison)
# ============================================================
#
# In Apex, you'd model these as inner classes for JSON.deserialize, since
# you'd typically be calling Tooling API from another Salesforce org (rare
# but real for tooling/devops orgs):
#
#    public class ToolingResponse {
#        // No generics in Apex — you write one wrapper PER record type:
#        public Integer totalSize;
#        public Boolean done;
#        public List<ApexClassRecord> records;
#        public String nextRecordsUrl;
#    }
#
#    public class ApexClassRecord {
#        public Attributes attributes;
#        public String Id;
#        public String Name;
#        public Decimal ApiVersion;
#        public String Status;
#        public Boolean IsValid;
#        public Integer LengthWithoutComments;
#        public String NamespacePrefix;
#        public String Body;
#        public Datetime CreatedDate;
#        public Datetime LastModifiedDate;
#    }
#
#    public class Attributes {
#        public String type;
#        public String url;
#    }
#
# You'd then need: ApexTriggerToolingResponse, CustomFieldToolingResponse,
# etc. — one wrapper per record type. Six record types = six wrappers,
# each duplicating totalSize/done/records boilerplate.
#
# Concept mapping:
# - TypeVar("T", bound=BaseModel)             → Apex has no generics for
#                                                user-defined types — you
#                                                duplicate the wrapper
# - Generic[T] + class[T]                     → Apex inner class per record
#                                                type (6x the boilerplate)
# - Optional[str] = None                       → public String (Apex defaults
#                                                to null; no compile-time
#                                                Optional)
# - Pydantic ignores unknown fields by default → JSON.deserialize requires
#                                                strict shape OR you use
#                                                JSON.deserializeUntyped
#                                                and lose type safety
# - datetime parsing                          → Apex Datetime fields parse
#                                                ISO-8601 automatically via
#                                                JSON.deserialize
# - Field validation at parse time            → Apex has no equivalent —
#                                                you check field by field
#                                                after deserialize
#
# This is a clear win for Python: 6 record models share ONE response
# envelope via Generic[T]. Apex makes you duplicate the envelope 6 times
# because the type system can't express "wrapper of T."
# ============================================================