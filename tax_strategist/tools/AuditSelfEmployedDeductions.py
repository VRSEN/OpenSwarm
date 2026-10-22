import json

from agency_swarm.tools import BaseTool
from pydantic import Field

COMMON_DEDUCTIONS = {
    "home_office": "Home office deduction (simplified or actual)",
    "vehicle_miles": "Business mileage at IRS standard rate",
    "health_insurance": "Self-employed health insurance deduction",
    "retirement": "SEP-IRA or Solo 401(k) contributions",
    "software": "Business software and subscriptions",
    "professional_services": "Accounting, legal, consulting fees",
    "education": "Business-related training and courses",
    "phone_internet": "Business portion of phone and internet",
    "supplies": "Office supplies and equipment",
    "travel": "Business travel (not commuting)",
    "meals": "Business meals (typically 50% deductible)",
}


class AuditSelfEmployedDeductions(BaseTool):
    """
    Checklist audit of common self-employed deductions against user-reported expenses.
    """

    expense_categories: dict[str, float] = Field(
        ...,
        description="Mapping of category name to amount spent (e.g., {'software': 2400}).",
    )
    home_office_sqft: float = Field(default=0, ge=0, description="Square feet used exclusively for business.")
    business_miles: float = Field(default=0, ge=0, description="Business miles driven this year.")
    has_separate_business_phone: bool = Field(default=False, description="Dedicated business phone line.")

    def run(self) -> str:
        if not self.expense_categories:
            return json.dumps({"error": "expense_categories cannot be empty."})

        reported_keys = {k.lower().replace(" ", "_") for k in self.expense_categories}
        found = []
        missing = []
        flags = []

        alias_map = {
            "home_office": ["home_office", "rent", "utilities"],
            "vehicle_miles": ["vehicle", "mileage", "gas", "car"],
            "health_insurance": ["health", "insurance", "medical"],
            "retirement": ["retirement", "401k", "sep", "ira"],
            "software": ["software", "saas", "tools"],
            "professional_services": ["accounting", "legal", "cpa", "lawyer"],
            "phone_internet": ["phone", "internet", "telecom"],
        }

        for deduction_key, description in COMMON_DEDUCTIONS.items():
            aliases = alias_map.get(deduction_key, [deduction_key])
            matched = any(a in reported_keys or a in k for k in reported_keys for a in aliases)
            if matched:
                found.append({"deduction": deduction_key, "description": description})
            else:
                missing.append({"deduction": deduction_key, "description": description})

        if self.home_office_sqft == 0 and "home_office" not in str(reported_keys):
            flags.append("No home office sqft provided—may be missing home office deduction.")

        if self.business_miles == 0:
            flags.append("Zero business miles—confirm if you drive for client work.")

        if not self.has_separate_business_phone and "phone" not in str(reported_keys):
            flags.append("Consider allocating business % of phone bill if no separate line.")

        total_reported = sum(self.expense_categories.values())
        top_category = max(self.expense_categories, key=self.expense_categories.get)
        if self.expense_categories[top_category] / total_reported > 0.6:
            flags.append(
                f"Over 60% of expenses in '{top_category}'—ensure documentation supports concentration."
            )

        mileage_deduction = round(self.business_miles * 0.70, 2)  # 2026 IRS rate placeholder

        result = {
            "total_reported_expenses": round(total_reported, 2),
            "categories_reported": self.expense_categories,
            "deductions_found": found,
            "deductions_missing": missing,
            "flags": flags,
            "estimated_mileage_deduction": mileage_deduction if self.business_miles > 0 else 0,
            "documentation_checklist": [
                "Receipts for expenses > $75",
                "Mileage log with date, destination, purpose",
                "Home office floor plan if claiming dedicated space",
                "1099-NEC and 1099-K records for income reconciliation",
            ],
        }
        return json.dumps(result, indent=2)


if __name__ == "__main__":
    tool = AuditSelfEmployedDeductions(
        expense_categories={"software": 3200, "accounting": 1800, "travel": 950},
        business_miles=4200,
        home_office_sqft=120,
    )
    print(tool.run())
