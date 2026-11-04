"""The public proof must have the complete agreed type, in addition to an axiom audit."""


def audit_text(design):
    if design not in ("baseline","candidate"):
        raise ValueError("unknown design")
    return f"""import Task2.{design.title()}
namespace Task2.PublicAudit
theorem claim_type_check : Task2.Implements Task2.Imported.{design} Task2.sourceEval :=
  Task2.{design}_correct
end Task2.PublicAudit
#check Task2.{design}_correct
#print axioms Task2.{design}_correct
#print axioms Task2.PublicAudit.claim_type_check
"""
