import Task2.Baseline
namespace Task2.PublicAudit
theorem claim_type_check : Task2.Implements Task2.Imported.baseline Task2.sourceEval :=
  Task2.baseline_correct
end Task2.PublicAudit
#check Task2.baseline_correct
#print axioms Task2.baseline_correct
#print axioms Task2.PublicAudit.claim_type_check
