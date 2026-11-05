# Shelf tool script (Python). Context: SOP viewer.
import hou, toolutils

# EXACT HDA type name incl. namespace/version, e.g. "pete::edge_bezier::1.0"
# find it: hou.selectedNodes()[0].type().name()
TYPE = "piotr::bz_curve::1.2"

def find_solve(node):
    """Inner wrangle: named 'solve', else first attribwrangle found."""
    s = node.node("solve")
    if s is None:
        for c in node.allSubChildren():
            if c.type().name().startswith("attribwrangle"):
                return c
    return s

def read_detail_vec(sop, name):
    """Read a float3 detail attrib without touching hou.Geometry (robust across recooks)."""
    p = sop.path()
    return tuple(hou.hscriptExpression('detail("%s", "%s", %d)' % (p, name, i)) for i in range(3))


def init_from_solve(node, solve):
    """ends = original points, mids = 1/3, 2/3. Returns True on success."""
    node.parm("custom_handles").set(0)
    solve.cook(force=True)
    if solve.errors():
        print("bz_curve: solve has errors:", solve.errors())
        return False
    vals = {}
    for parm, attr in (("start_pos", "bz_o0"), ("handle1", "bz_d1"),
                       ("handle2", "bz_d2"), ("end_pos", "bz_o3")):
        vals[parm] = read_detail_vec(solve, attr)
    for parm, v in vals.items():
        node.parmTuple(parm).set(v)
    node.parm("custom_handles").set(1)
    return True

sv = toolutils.sceneViewer()
sel = sv.selectGeometry("Select connected edge chain, Enter to confirm",
                        geometry_types=(hou.geometryType.Edges,),
                        use_existing_selection=True, consume_selections=True)
nodes = sel.nodes()
src = nodes[0] if nodes else hou.selectedNodes()[0]
if isinstance(src, hou.ObjNode):          # selection came back at obj level
    src = src.displayNode()
if not isinstance(src, hou.SopNode):
    raise hou.Error("Source isn't a SOP: %s" % src.path())
if hou.nodeType(hou.sopNodeTypeCategory(), TYPE) is None:
    raise hou.Error("No SOP type '%s' (wrong category or not installed)" % TYPE)

with hou.undos.group("Edge Bezier"):
    n = src.createOutputNode(TYPE)
    n.parm("edges").set(sel.mergedSelectionString(empty_string_selects_all=False,
                                                  force_numeric=True))
    n.setDisplayFlag(True); n.setRenderFlag(True); n.setCurrent(True, clear_all_selected=True)
    n.moveToGoodPosition()

    # init handles: ends = original points, mids = 1/3, 2/3
    solve = find_solve(n)
    if solve is None:
        raise hou.Error("No wrangle found inside %s" % n.path())
    init_from_solve(n, solve)

sv.enterCurrentNodeState()
