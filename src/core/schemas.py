from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field

class TimeUnit(str, Enum):
    FLIGHT_HOURS = "flight_hours"
    FLIGHT_CYCLES = "flight_cycles"
    DAYS = "days"
    MONTHS = "months"
    YEARS = "years"
    CALENDAR_DATE = "calendar_date"


class NumericRange(BaseModel):
    start: Optional[int] = Field(
        default=None,
        description=(
            "Lower bound of the MSN range (inclusive by default). "
            "Set to None if there is no lower bound."
        )
    )
    end: Optional[int] = Field(
        default=None,
        description=(
            "Upper bound of the MSN range (inclusive by default). "
            "Set to None if there is no upper bound."
        )
    )
    inclusive_start: bool = Field(
        default=True,
        description="True means >= (greater than or equal to start). False means > (strictly greater than)."
    )
    inclusive_end: bool = Field(
        default=True,
        description="True means <= (less than or equal to end). False means < (strictly less than)."
    )


class MSNConstraint(BaseModel):
    all: Optional[bool] = Field(
        default=None,
        description=(
            "Set to True when the AD explicitly states 'all manufacturer serial numbers (MSN)' or 'all MSN'. "
            "IMPORTANT: Never leave this None when the AD explicitly uses the word 'all' for MSN applicability — "
            "even if other exclusions apply, the 'all' inclusion must still be captured here. "
            "Leave None only when applicability is defined purely by a specific range or list."
        )
    )
    range: Optional[NumericRange] = Field(
        default=None,
        description=(
            "A continuous numeric range of MSNs this constraint covers. "
            "Use when the AD specifies a span like 'MSN 100 through MSN 500'. "
            "Do not use together with specific_msns."
        )
    )
    specific_msns: Optional[List[int]] = Field(
        default=None,
        description=(
            "An explicit list of individual MSN integers this constraint covers. "
            "Use when the AD names specific serial numbers, e.g. 'MSN 364 or MSN 385'. "
            "Do not use together with range."
        )
    )
    excluded: bool = Field(
        default=False,
        description=(
            "Set to True when these MSNs are EXCLUDED from applicability "
            "(AD language like 'except MSN...', 'excluding MSN...'). "
            "Set to False when these MSNs are positively INCLUDED in applicability. "
            "Default is False (inclusion)."
        )
    )


class ModificationConstraint(BaseModel):
    modification_id: str = Field(
        description=(
            "The exact modification identifier as written in the AD. "
            "Always an Airbus 'mod' number, e.g. 'mod 24591', 'mod 24977'. "
            "IMPORTANT: Modification numbers are never Service Bulletins — "
            "do not confuse with SB identifiers (e.g. 'A320-57-XXXX'). "
            "Copy the identifier verbatim from the AD text."
        )
    )
    embodied: Optional[bool] = Field(
        default=None,
        description=(
            "True = this modification IS embodied on the aircraft. "
            "False = this modification is NOT embodied on the aircraft. "
            "None = embodiment status is unspecified or not relevant to this constraint."
        )
    )
    excluded: bool = Field(
        default=False,
        description=(
            "Set to True when aircraft WITH this modification embodied are EXCLUDED from applicability "
            "(AD language like 'except those on which mod XXXXX has been embodied in production'). "
            "Set to False when this modification is a positive inclusion condition. "
            "Default is False (inclusion)."
        )
    )


class ServiceBulletinConstraint(BaseModel):
    sb_identifier: str = Field(
        description=(
            "The exact Service Bulletin identifier as written in the AD, "
            "e.g. 'A320-57-1089', 'A320-57-1100'. "
            "IMPORTANT: Only actual Airbus Service Bulletins belong here (format: 'AXXX-XX-XXXX'). "
            "Airbus modification numbers ('mod XXXXX') must NEVER be placed here — "
            "those belong exclusively in ModificationConstraint. "
            "Copy the identifier verbatim from the AD text, without the 'SB' prefix."
        )
    )
    revision: Optional[str] = Field(
        default=None,
        description=(
            "The revision qualifier for this SB constraint, exactly as stated in the AD. "
            "Examples: 'Revision 04', 'any revision lower than Revision 04', 'Revision 03 or later'. "
            "Leave None if no specific revision is mentioned and any revision applies."
        )
    )
    incorporated: Optional[bool] = Field(
        default=None,
        description=(
            "True = this SB HAS been incorporated on the aircraft. "
            "False = this SB has NOT been incorporated on the aircraft. "
            "None = incorporation status is unspecified or not relevant to this constraint."
        )
    )
    excluded: bool = Field(
        default=False,
        description=(
            "Set to True when aircraft on which this SB HAS been embodied are EXCLUDED from applicability "
            "(AD language like 'except those on which SB XXXX has been embodied'). "
            "Set to False when this SB is a positive inclusion or compliance condition. "
            "Default is False (inclusion)."
        )
    )


class AircraftGroup(BaseModel):
    group_id: str = Field(
        description=(
            "The group label exactly as defined in the AD's Groups section. "
            "Examples: 'Group 1', 'Group 2', 'Group A', 'Group B'. "
            "Use verbatim from the AD — do not invent or rename groups."
        )
    )
    models: Optional[List[str]] = Field(
        default=None,
        description=(
            "Aircraft model variants that belong to this group, "
            "derived from the group definition. "
            "Examples: ['A321-111', 'A321-112'] or ['A320']. "
            "Leave None if the group definition does not restrict by model "
            "(i.e. it applies to all models already listed in the top-level applicability)."
        )
    )
    msn_constraints: Optional[List[MSNConstraint]] = Field(
        default=None,
        description=(
            "MSN-based constraints that define or restrict membership in this group. "
            "Apply the same rules as top-level msn_constraints: "
            "if the group definition says 'all MSN', populate with MSNConstraint(all=True, excluded=False). "
            "If the group is defined by specific MSNs, list them in specific_msns. "
            "Leave None only if MSN is not a factor in this group's definition."
        )
    )
    modification_constraints: Optional[List[ModificationConstraint]] = Field(
        default=None,
        description=(
            "Modification-based constraints that define or exclude aircraft from this group. "
            "Only use ModificationConstraint here — never mix with SB identifiers. "
            "Examples: a group excluding aircraft with a specific mod embodied in production. "
            "Leave None if modifications are not a factor in this group's definition."
        )
    )
    sb_constraints: Optional[List[ServiceBulletinConstraint]] = Field(
        default=None,
        description=(
            "Service Bulletin constraints that define or exclude aircraft from this group. "
            "Only use actual SB identifiers here — never use mod numbers. "
            "Example: a group defined by aircraft on which a specific SB has NOT been embodied. "
            "Leave None if SBs are not a factor in this group's definition."
        )
    )
    description: Optional[str] = Field(
        default=None,
        description=(
            "Free-text fallback for group membership logic that cannot be fully expressed "
            "by the structured fields above. "
            "Transcribe the exact defining sentence from the AD. "
            "Always populate this field — it serves as a human-readable audit trail "
            "even when structured fields are also populated."
        )
    )


class ComplianceTime(BaseModel):
    value: Optional[int] = Field(
        default=None,
        description=(
            "The numeric value of this compliance time. Always a positive integer. "
            "Examples: 37300 for '37 300 flight hours', 24 for '24 months', 90 for '90 days'. "
            "Set to None only when a specific calendar_date is used instead of a relative time value."
        )
    )
    unit: Optional[TimeUnit] = Field(
        default=None,
        description=(
            "The unit of measurement corresponding to value. "
            "Must be one of the TimeUnit enum values. "
            "Set to None only when calendar_date is used instead of value+unit."
        )
    )
    reference: Optional[str] = Field(
        default=None,
        description=(
            "The reference point from which this time is measured, transcribed from the AD. "
            "Examples: 'since first flight of the aeroplane', "
            "'after the effective date of this AD', "
            "'since the last inspection', "
            "'from the effective date of this AD'. "
            "Leave None only if no reference point is stated and the context is self-evident."
        )
    )
    calendar_date: Optional[str] = Field(
        default=None,
        description=(
            "An absolute calendar deadline in ISO 8601 format (YYYY-MM-DD). "
            "Use only when the AD specifies a hard date rather than a relative time window. "
            "When populated, value and unit should be None. "
            "Example: '2026-06-01' for 'before 01 June 2026'."
        )
    )
    is_interval: bool = Field(
        default=False,
        description=(
            "Set to True for RECURRING intervals between repeated actions "
            "(AD language like 'thereafter, at intervals not exceeding X FH'). "
            "Set to False for one-time initial thresholds "
            "(AD language like 'before exceeding X FH since first flight'). "
            "Default is False."
        )
    )


class RequirementAction(BaseModel):
    paragraph_id: str = Field(
        description=(
            "The paragraph identifier exactly as numbered in the AD's Required Actions section. "
            "Examples: '(1)', '(5)', '(8)', '(12)'. "
            "Used to cross-reference paragraphs (e.g. corrective actions referencing their "
            "triggering inspection paragraph)."
        )
    )
    action_type: str = Field(
        description=(
            "The category of this required action. Use exactly one of the following values: "
            "'inspection' — any DET, GVI, SDI, ESDI, or other inspection task; "
            "'modification' — a structural, design, or configuration change to the aircraft; "
            "'corrective_action' — a repair or follow-up action triggered by a finding during inspection; "
            "'terminating_action' — an action whose accomplishment ends one or more repetitive requirements; "
            "'prohibition' — an action that must NOT be accomplished (e.g. 'do not embody SB X below Rev Y'); "
            "'clarification' — a paragraph that clarifies scope or interaction between other paragraphs "
            "without itself requiring a physical action (e.g. 'accomplishment of paragraph X does not "
            "terminate paragraph Y')."
        )
    )
    applies_to_groups: Optional[List[str]] = Field(
        default=None,
        description=(
            "List of group IDs, exactly as defined in the AD's Groups section, "
            "to which this requirement applies. "
            "Examples: ['Group 1'], ['Group 1', 'Group 4']. "
            "Leave None if the requirement is stated in terms of direct model references "
            "rather than group labels, or if it applies implicitly to all groups "
            "(e.g. clarification paragraphs)."
        )
    )
    applies_to_models: Optional[List[str]] = Field(
        default=None,
        description=(
            "Direct aircraft model references for requirements that do not use group labels. "
            "Examples: ['A320-211', 'A320-212']. "
            "Leave None when applies_to_groups is populated — do not duplicate the same "
            "applicability in both fields."
        )
    )
    additional_applicability_condition: Optional[str] = Field(
        default=None,
        description=(
            "Any further condition within the stated group or model scope that narrows "
            "which aircraft this paragraph applies to, transcribed verbatim from the AD. "
            "Use when the paragraph adds a qualifier beyond the group definition itself. "
            "Examples: "
            "'except aeroplanes modified in accordance with the instructions of Airbus SB A320-57-1100', "
            "'having embodied SB A320-57-1089 at any revision lower than Revision 04 (for Group 4 aeroplanes)'. "
            "Leave None if no additional condition is stated."
        )
    )
    description: str = Field(
        description=(
            "A concise, self-contained human-readable summary of what action must be performed. "
            "Include: the inspection method or action type (e.g. DET, GVI, modification), "
            "the area or component involved, and the reference document(s) to follow. "
            "Write in plain language suitable for a maintenance engineer to understand at a glance. "
            "Example: 'Accomplish a detailed inspection (DET) of the LH and RH wing inner rear spars "
            "at the MLG anchorage fitting attachment holes, per SB A320-57-1101 Revision 04.'"
        )
    )
    compliance_times: Optional[List[ComplianceTime]] = Field(
        default=None,
        description=(
            "One or more initial compliance thresholds by which this action must first be accomplished. "
            "When the AD states multiple limits with 'whichever occurs first', "
            "list each as a separate ComplianceTime entry — the whichever-first logic is implied "
            "by multiple entries in this list. "
            "Example: '37 300 FH or 20 000 FC whichever occurs first since first flight' → "
            "two ComplianceTime entries: one for 37300 FH and one for 20000 FC, "
            "both with reference 'since first flight of the aeroplane' and is_interval=False. "
            "Leave None for clarification paragraphs or terminating action notes with no time limit."
        )
    )
    interval: Optional[List[ComplianceTime]] = Field(
        default=None,
        description=(
            "One or more recurring intervals for repetitive requirements. "
            "Populate only when the AD states 'thereafter, at intervals not exceeding...'. "
            "As with compliance_times, list each limit as a separate ComplianceTime entry "
            "when multiple limits apply with 'whichever occurs first'. "
            "All entries must have is_interval=True. "
            "Leave None for one-time actions (modifications, one-time inspections, corrective actions)."
        )
    )
    reference_documents: Optional[List[str]] = Field(
        default=None,
        description=(
            "List of Airbus Service Bulletins or other technical documents whose instructions "
            "must be followed to accomplish this action. "
            "Include the revision where the AD specifies it. "
            "Examples: ['SB A320-57-1101 Revision 04', 'SB A320-57-1256']. "
            "Leave None for corrective actions where the repair instructions are obtained "
            "from Airbus on a case-by-case basis, or for clarification paragraphs."
        )
    )
    triggered_by_paragraph: Optional[str] = Field(
        default=None,
        description=(
            "For corrective_action paragraphs only: the paragraph_id of the inspection "
            "or action that triggers this corrective action when discrepancies are found. "
            "Example: '(1)' means this corrective action is triggered by findings during "
            "the inspection required by paragraph (1). "
            "Leave None for all non-corrective action types."
        )
    )
    terminating_action_for: Optional[List[str]] = Field(
        default=None,
        description=(
            "List of paragraph_ids whose repetitive requirements are permanently terminated "
            "upon accomplishment of this action. "
            "Example: ['(5)'] means completing this action ends the recurring inspections "
            "required by paragraph (5) for that aircraft. "
            "Leave None if this action has no terminating effect on other paragraphs. "
            "Note: also set is_terminating_action=True when this field is populated."
        )
    )
    is_terminating_action: bool = Field(
        default=False,
        description=(
            "Set to True if accomplishing this action permanently terminates one or more "
            "repetitive requirements in this AD. "
            "Must be True whenever terminating_action_for is populated. "
            "Default is False."
        )
    )


class ADApplicabilityExtraction(BaseModel):
    ad_number: str = Field(
        description=(
            "The full AD identifier including any revision suffix, exactly as it appears in the AD header. "
            "Examples: '2025-0254R1', '2023-0041', 'AD 2021-23-10'. "
            "Never omit the revision suffix if present."
        )
    )
    issuing_authority: Optional[str] = Field(
        default=None,
        description=(
            "The aviation authority that issued this AD. "
            "Examples: 'EASA', 'FAA', 'TCCA', 'CASA'. "
            "Taken from the AD header or introductory paragraph."
        )
    )
    effective_date: Optional[str] = Field(
        default=None,
        description=(
            "The effective date of this AD (or its most recent revision) in ISO 8601 format (YYYY-MM-DD). "
            "If multiple dates are listed (original issue and revision), use the revision's effective date. "
            "Example: '2025-12-08'."
        )
    )
    revision: Optional[str] = Field(
        default=None,
        description=(
            "The revision label of this AD exactly as stated in the document. "
            "Examples: 'Revision 01', 'R1', 'Amendment 2'. "
            "Leave None for original issue (no revision)."
        )
    )
    supersedes: Optional[List[str]] = Field(
        default=None,
        description=(
            "List of AD identifiers that this AD supersedes, replaces, or revises, "
            "taken from the Revision field or the Reason section. "
            "Include all superseded ADs, not just the immediate predecessor. "
            "Examples: ['2025-0254', '2007-0162', '2014-0169']. "
            "Leave None if this is a first-issue AD that supersedes nothing."
        )
    )
    models: Optional[List[str]] = Field(
        default=None,
        description=(
            "Complete list of every aircraft model variant explicitly named in the "
            "Applicability section of the AD. "
            "List each variant as a separate string, exactly as written. "
            "Examples: ['A320-211', 'A320-212', 'A320-214', 'A321-111', 'A321-112']. "
            "Do not collapse variants (e.g. do not write 'A320' if the AD lists 'A320-211', 'A320-212' etc.)."
        )
    )
    msn_constraints: Optional[List[MSNConstraint]] = Field(
        default=None,
        description=(
            "Top-level MSN constraints covering the entire AD applicability, before any group scoping. "
            "IMPORTANT — never leave this None when the AD mentions MSN applicability: "
            "If the AD says 'all manufacturer serial numbers (MSN)' or 'all MSN', "
            "always populate with at least one MSNConstraint(all=True, excluded=False). "
            "If specific MSN ranges or numbers are excluded (e.g. 'except MSN 001 to 099'), "
            "add a separate MSNConstraint with excluded=True for those. "
            "Only leave None if the AD makes absolutely no reference to MSN applicability."
        )
    )
    modification_constraints: Optional[List[ModificationConstraint]] = Field(
        default=None,
        description=(
            "Top-level Airbus modification constraints covering the entire AD applicability. "
            "IMPORTANT: Only 'mod XXXXX' numbers belong here — never SB identifiers. "
            "These are almost always exclusions: aircraft on which a specific mod has been "
            "embodied in production are excluded from the AD's scope. "
            "Capture each mod as a separate ModificationConstraint. "
            "Example: 'except those on which Airbus mod 24591 has been embodied in production' → "
            "ModificationConstraint(modification_id='mod 24591', embodied=True, excluded=True). "
            "Leave None only if no modification-based applicability constraints exist in this AD."
        )
    )
    sb_constraints: Optional[List[ServiceBulletinConstraint]] = Field(
        default=None,
        description=(
            "Top-level Service Bulletin constraints covering the entire AD applicability. "
            "IMPORTANT: Only actual Airbus SB identifiers (format 'AXXX-XX-XXXX') belong here. "
            "Airbus modification numbers ('mod XXXXX') must NEVER be placed here — "
            "those belong exclusively in modification_constraints. "
            "These are typically SB-based exclusions, e.g. aircraft on which a specific SB "
            "revision has been embodied are excluded from scope. "
            "Example: 'except those on which SB A320-57-1089 at Revision 04 has been embodied' → "
            "ServiceBulletinConstraint(sb_identifier='A320-57-1089', revision='Revision 04', "
            "incorporated=True, excluded=True). "
            "Leave None only if no SB-based applicability constraints exist in this AD."
        )
    )
    compliance_time: Optional[List[ComplianceTime]] = Field(
        default=None,
        description=(
            "Top-level summary of the most immediate compliance deadline(s) imposed by this AD as a whole. "
            "The intent is to surface the AD's urgency at a glance, without requiring a consumer "
            "to parse every RequirementAction. "
            "Populate with the most restrictive (shortest) initial deadline across all requirements. "
            "When the shortest deadline is expressed as 'X or Y whichever occurs first', "
            "list both as separate ComplianceTime entries. "
            "This field is a summary — full per-paragraph compliance times are still "
            "captured in each RequirementAction.compliance_times. "
            "Leave None only if this AD contains no time-limited requirements "
            "(e.g. a purely prohibitive AD with no deadline)."
        )
    )
    groups: Optional[List[AircraftGroup]] = Field(
        default=None,
        description=(
            "Definitions of all aircraft groups declared in the AD's Groups section, "
            "one AircraftGroup entry per defined group. "
            "Groups are internal AD constructs that partition applicable aircraft for "
            "the purpose of applying different requirements to different subsets. "
            "Preserve the exact group labels and definitions from the AD. "
            "Leave None only if the AD does not define any named groups."
        )
    )
    requirements: Optional[List[RequirementAction]] = Field(
        default=None,
        description=(
            "Complete list of all required actions, one RequirementAction per numbered paragraph "
            "in the AD's Required Actions section. "
            "This is the primary output of the extraction. "
            "Every paragraph must be captured — inspections, modifications, corrective actions, "
            "prohibitions, terminating actions, and clarification notes alike. "
            "Preserve paragraph numbering exactly as in the AD. "
            "Leave None only if the AD contains no required actions (which should never occur "
            "for a valid AD)."
        )
    )