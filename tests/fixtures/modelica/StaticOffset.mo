model StaticOffset
  parameter Real c = 1.0;
  Modelica.Blocks.Interfaces.RealInput u;
  Modelica.Blocks.Interfaces.RealOutput y;
equation
  y = u + c;
end StaticOffset;