model Gain
  parameter Real k = 2.0;
  Modelica.Blocks.Interfaces.RealInput u;
  Modelica.Blocks.Interfaces.RealOutput y;
equation
  y = k * u;
end Gain;