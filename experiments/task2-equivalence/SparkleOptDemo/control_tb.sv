`timescale 1ns/1ps
module tb_control;
  logic clock = 0;
  logic reset = 1;
  logic in3_valid = 0;
  wire in3_ready, out0_valid, in2_st0_done_ready, in2_st0_valid;
  struct packed { logic [31:0] data; } in2_st0;
  logic [31:0] a_mem [0:15], b_mem [0:15];
  logic [31:0] expected;
  string a_path, b_path, trace_path;
  integer trace_file;
  integer edge_number = 0;

  main dut(
    .clock(clock), .reset(reset), .in3_valid(in3_valid), .in3_ready(in3_ready),
    .in2_st0_done_valid(1'b0), .out0_ready(1'b1), .in2_st0_ready(1'b1),
    .out0_valid(out0_valid), .in2_st0_done_ready(in2_st0_done_ready),
    .in2_st0(in2_st0), .in2_st0_valid(in2_st0_valid)
  );
  always #5 clock = ~clock;
  always_ff @(posedge clock) begin
    if (reset) in3_valid <= 1;
    else if (in3_ready) in3_valid <= 0;
  end

  initial begin
    if (!$value$plusargs("A=%s", a_path) || !$value$plusargs("B=%s", b_path) ||
        !$value$plusargs("TRACE=%s", trace_path) || !$value$plusargs("EXPECTED=%h", expected))
      $fatal(1, "Supply complete-word inputs, expected word and trace path");
    $readmemh(a_path, a_mem);
    $readmemh(b_path, b_mem);
    for (int i = 0; i < 16; i++) begin
      dut.\handshake_memory0._handshake_memory_5 [i] = a_mem[i];
      dut.\handshake_memory1._handshake_memory_4 [i] = b_mem[i];
    end
    trace_file = $fopen(trace_path, "w");
    if (!trace_file) $fatal(1, "Could not open trace output");
    $fwrite(trace_file, "cycle,reset,in3_valid,in3_ready,out0_valid,in2_st0_done_ready,in2_st0_valid,in2_st0_ready,in2_st0\n");
    #40 reset = 0;
  end

  // Sample before nonblocking state updates, exactly as the existing testbench.
  always @(posedge clock) begin
    $fwrite(trace_file, "%0d,%0d,%0d,%0d,%0d,%0d,%0d,1,%0d\n", edge_number,
      reset, in3_valid, in3_ready, out0_valid, in2_st0_done_ready, in2_st0_valid, in2_st0.data);
    if (!reset && in2_st0_valid) begin
      if (in2_st0.data !== expected) $fatal(1, "Payload mismatch: expected %h got %h", expected, in2_st0.data);
      $fclose(trace_file);
      $display("PASS control expected=%h got=%h edge=%0d", expected, in2_st0.data, edge_number);
      $finish;
    end
    if (edge_number > 10000) $fatal(1, "Control simulation timed out");
    edge_number = edge_number + 1;
  end
endmodule
