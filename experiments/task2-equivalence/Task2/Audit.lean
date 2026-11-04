import Task2.Baseline

namespace Task2.Audit
theorem baseline_claim : Task2.Implements Task2.Imported.baseline Task2.sourceEval :=
  Task2.baseline_correct
end Task2.Audit

#check Task2.baseline_correct
#print axioms Task2.baseline_correct
#print axioms Task2.Audit.baseline_claim
