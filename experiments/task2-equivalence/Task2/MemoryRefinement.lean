import Task2.WordDot

namespace Task2.MemoryRefinement

def blend (old data mask : Word) : Word :=
  (old &&& ~~~mask) ||| (data &&& mask)

def padded (word extra : Word) : BitVec 1 → Word :=
  fun address => if address == 0 then word else extra

def writeZero (memory : BitVec 1 → Word) (data mask : Word) : BitVec 1 → Word :=
  fun address => if address == 0 then blend (memory 0) data mask else memory address

theorem read_zero (word extra : Word) : padded word extra 0 = word := by rfl

theorem write_zero (memory : BitVec 1 → Word) (data mask : Word) :
    writeZero memory data mask 0 = blend (memory 0) data mask := by rfl

theorem extra_unchanged (memory : BitVec 1 → Word) (data mask : Word) :
    writeZero memory data mask 1 = memory 1 := by rfl

/-- Generic memory primitive law; checking source clock/addresses stays in the importer boundary. -/
def clockedWrite (previous current enable : Bool) (memory : BitVec 1 → Word) (data mask : Word) :=
  if !previous && current && enable then writeZero memory data mask else memory

theorem positive_edge_lifting (enable : Bool) (memory : BitVec 1 → Word) (data mask : Word) :
    clockedWrite false true enable memory data mask =
      (if enable then writeZero memory data mask else memory) := by rfl

end Task2.MemoryRefinement
