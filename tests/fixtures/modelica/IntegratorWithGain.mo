model IntegratorWithGain
  Modelica.Blocks.Interfaces.RealInput u;
  Modelica.Blocks.Interfaces.RealOutput y;
protected
  Integrator integrator(gain = 1.0);
  Gain gain(k = 2.0);
equation
  connect(u, integrator.u);
  connect(integrator.y, gain.u);
  connect(gain.y, y);
end IntegratorWithGain;