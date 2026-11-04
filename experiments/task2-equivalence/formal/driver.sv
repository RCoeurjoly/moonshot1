module task2_compare # (parameter MUTATE_PAYLOAD = 0) (
  input clock,
  input [511:0] task2_words_a, task2_words_b,
  output accepted_valid,
  output [31:0] accepted_data
);
  reg [9:0] driver_cycle = 0;
  reg driver_start;
  reg seen_payload = 0;
  reg past_inputs_valid = 0;
  reg [511:0] past_words_a, past_words_b;
  wire reset = driver_cycle < 4;
  wire start_ready, payload_valid;
  wire [31:0] payload_data;
  task2_design dut (
    .clock(clock), .reset(reset), .in3_valid(driver_start), .in3_ready(start_ready),
    .out0_ready(1'b1), .in2_st0_ready(1'b1), .in2_st0_done_valid(1'b0),
    .out0_valid(), .in2_st0_done_ready(), .in2_st0_valid(payload_valid), .in2_st0(payload_data),
    .task2_words_a(task2_words_a), .task2_words_b(task2_words_b)
  );
  always @(posedge clock) begin
    past_inputs_valid <= 1;
    past_words_a <= task2_words_a;
    past_words_b <= task2_words_b;
    if (driver_cycle < 512) driver_cycle <= driver_cycle + 1;
    if (reset) driver_start <= 1;
    else if (start_ready) driver_start <= 0;
    if (!reset && payload_valid) seen_payload <= 1;
  end
  always @* if (past_inputs_valid) begin
    assume(task2_words_a == past_words_a);
    assume(task2_words_b == past_words_b);
  end
  assign accepted_valid = !reset && !seen_payload && payload_valid;
  assign accepted_data = accepted_valid ? (payload_data ^ (MUTATE_PAYLOAD ? 32'd1 : 32'd0)) : 32'd0;
endmodule
