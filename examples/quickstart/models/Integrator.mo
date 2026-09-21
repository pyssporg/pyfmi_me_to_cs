model Integrator
  parameter Real gain = 1.0;
  Modelica.Blocks.Interfaces.RealInput u;
  Modelica.Blocks.Interfaces.RealOutput y;
protected
  Real x(start = 0.0);
equation
  der(x) = gain * u;
  y = x;
end Integrator;