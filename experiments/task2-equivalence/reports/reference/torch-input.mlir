module {
  func.func @main(%arg0: !torch.vtensor<[16],si32>, %arg1: !torch.vtensor<[16],si32>) -> !torch.vtensor<[],si32> {
    %0 = torch.aten.matmul %arg0, %arg1 : !torch.vtensor<[16],si32>, !torch.vtensor<[16],si32> -> !torch.vtensor<[],si32>
    return %0 : !torch.vtensor<[],si32>
  }
}
