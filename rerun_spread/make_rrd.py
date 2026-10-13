import math, random, shutil, sys
import panel as pn
import bencher as bn
random.seed(0)
print("bencher from", bn.__file__)
captured = {}
def capture(path, **kw):
    captured["path"] = path; return pn.pane.Markdown("x")
import bencher.utils_rrd as u; u.rrd_file_to_pane = capture
import bencher.results.rerun_result as rr
for name in dir(rr):
    if name == "rrd_file_to_pane":
        setattr(rr, name, capture)
class S(bn.ParametrizedSweep):
    x = bn.FloatSweep(default=0, bounds=[0, math.pi], samples=20)
    out = bn.ResultFloat()
    def benchmark(self):
        self.out = math.sin(self.x) + random.gauss(0, 0.05 + 0.2*abs(math.cos(self.x)))
res = S().to_bench(bn.BenchRunCfg(repeats=8, backend="rerun", cache_results=False, cache_samples=False)).plot_sweep(input_vars=["x"], result_vars=["out"], plot_callbacks=False)
res.to_rerun(result_var="out")
print(captured["path"])
shutil.copy(captured["path"], sys.argv[1])
