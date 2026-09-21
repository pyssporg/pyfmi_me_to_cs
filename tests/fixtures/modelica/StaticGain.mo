model StaticGain
  parameter Real k = 0.5;
  Modelica.Blocks.Interfaces.RealInput u;
  Modelica.Blocks.Interfaces.RealOutput y;
equation
  y = k * u;
end StaticGain;