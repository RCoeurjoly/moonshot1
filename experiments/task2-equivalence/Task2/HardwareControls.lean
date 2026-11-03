import Task2.Imported.BaselineAdapter

def main (args : List String) : IO Unit :=
  Task2.Trace.runControls Task2.Imported.BaselineAdapter.harness args
