import Task2.Source
import Task2.Imported.CandidateAdapter
import Task2.Imported.CandidateTraceCorrect

namespace Task2

theorem candidate_correct : Implements Imported.candidate sourceEval := by
  exact Imported.CandidateTrace.correct

end Task2
