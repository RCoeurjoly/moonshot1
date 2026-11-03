import Std

namespace Task2
abbrev Word := BitVec 32
abbrev Words := Fin 16 → Word

def dot32 (a b : Words) : Word :=
  (List.finRange 16).foldl (fun acc i => acc + a i * b i) 0

def prefixDot (a b : Words) (n : Nat) : Word :=
  ((List.finRange 16).take n).foldl (fun acc i => acc + a i * b i) 0

theorem prefixDot_complete (a b : Words) : prefixDot a b 16 = dot32 a b := by
  rfl
end Task2
