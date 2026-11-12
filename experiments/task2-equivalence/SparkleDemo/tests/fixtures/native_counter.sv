module native_counter(
  input clock,
  input reset,
  input [7:0] a,
  input [7:0] b,
  output reg [7:0] count,
  output [7:0] sum,
  output less
);
  always @(posedge clock)
    if (reset) count <= 8'd0;
    else count <= count + 8'd1;
  assign sum = a + b;
  assign less = $signed(a) < $signed(b);
endmodule
