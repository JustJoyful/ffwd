import sys, tvm
from tvm import relax, tirx
from mlc_llm.quantization import QUANTIZATION
q = QUANTIZATION["q4f16_1"]
bb = relax.BlockBuilder()
w = relax.Var("weight", relax.TensorType((256, 128), "float16"))
with bb.function(name="main", params=[w]):
    with bb.dataflow():
        lv = bb.emit_te(q._quantize, w, 1, False)
        gv = bb.emit_output(lv)
    bb.emit_func_output(gv)
mod = bb.finalize()
stage = sys.argv[1]
if stage == "print":
    print(mod.script()[:1500], flush=True)
mod = relax.transform.LegalizeOps()(mod)
print("legalized", flush=True)
if stage == "print2":
    print(mod.script()[:3000], flush=True)
if stage == "tirpipe":
    with tvm.target.Target("llvm"):
        mod = relax.get_pipeline("default")(mod)
    print("relax pipe ok", flush=True)
if stage == "build":
    ex = relax.build(mod, target="llvm", tir_pipeline="default"); print("BUILD OK", flush=True)
if stage == "passes":
    from tvm import s_tir, tirx
    from tvm.relax.vm_build import _filter_tir
    tm = _filter_tir(mod)
    tm = tirx.transform.BindTarget(tvm.target.Target("llvm").with_host(tvm.target.Target("llvm")))(tm)
    names = ["CanonicalizeLoop","LowerCrossThreadReduction","LowerInitBlock","PlanAndUpdateBufferAllocationLocation","ConvertBlocksToOpaque","LiftThreadBinding","ManifestSharedMemoryLocalStage","CompactBufferAllocation","LowerAutoCopy","UnifyThreadBinding","LowerMatchBuffer"]
    for n in names:
        print("run", n, flush=True)
        tm = getattr(s_tir.transform, n)()(tm)
    print("first group ok", flush=True)
    rest = [("s_tir","StmtSimplify") if False else ("tirx","StmtSimplify"),("s_tir","InjectPermutedLayout"),("s_tir","AnnotateIrregularLoop"),("s_tir","InjectSoftwarePipeline"),("s_tir","TransformMmaBufferLayout"),("s_tir","LowerOpaqueBlock"),("tirx","FlattenBuffer"),("tirx","BF16ComputeLegalize"),("tirx","NarrowDataType",32),("s_tir","LoopPartition"),("tirx","VectorizeLoop",True),("s_tir","InjectVirtualThread"),("s_tir","InjectDoubleBuffer"),("tirx","StorageRewrite"),("s_tir","HoistIfThenElse"),("tirx","UnrollLoop"),("s_tir","RenormalizeSplitPattern"),("tirx","StmtSimplify"),("tirx","RemoveNoOp"),("s_tir","RewriteUnsafeSelect"),("tirx","CommonSubexprElim"),("tirx","FP8ComputeLegalize"),("s_tir","VerifyVTCMLimit"),("s_tir","LowerVtcmAlloc"),("tirx","VerifyMemory"),("tirx","AnnotateEntryFunc"),("s_tir","ThreadSync","shared"),("s_tir","InferFragment"),("s_tir","LowerThreadAllreduce"),("s_tir","MergeSharedMemoryAllocations"),("tirx","SplitHostDevice"),("tirx","MakePackedAPI"),("tirx","FP8StorageLegalize"),("tirx","BF16StorageLegalize")]
    for t in rest:
        print("run", t, flush=True)
        ns = s_tir if t[0]=="s_tir" else tirx
        tm = getattr(ns.transform, t[1])(*t[2:])(tm)
    print("all passes ok", flush=True)
