import Task2.Source
import Task2.Imported.BaselineAdapter
import Task2.Imported.BaselineTraceCorrect

namespace Task2

theorem baseline_correct : Implements Imported.baseline sourceEval := by
  exact Imported.BaselineTrace.correct

end Task2
