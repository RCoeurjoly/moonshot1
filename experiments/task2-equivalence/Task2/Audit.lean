import Task2.Baseline
import Task2.Candidate

namespace Task2.Audit
theorem baseline_claim : Task2.Implements Task2.Imported.baseline Task2.sourceEval :=
  Task2.baseline_correct
theorem candidate_claim : Task2.Implements Task2.Imported.candidate Task2.sourceEval :=
  Task2.candidate_correct
end Task2.Audit

#check Task2.baseline_correct
#print axioms Task2.baseline_correct
#print axioms Task2.Audit.baseline_claim
#check Task2.candidate_correct
#print axioms Task2.candidate_correct
#print axioms Task2.Audit.candidate_claim
