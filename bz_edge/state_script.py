# HDA > Type Properties > Interactive > State Script (paste whole thing)
import hou

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

def init_handles(node):
    """Set start/end to original points, handles to 1/3 and 2/3. Returns True on success."""
    solve = find_solve(node)
    if solve is None:
        return False
    with hou.undos.group("Bezier: init handles"):
        return init_from_solve(node, solve)


class State(object):
    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self.node = None
        sv = scene_viewer
        self.curve = hou.GeometryDrawable(sv, hou.drawableGeometryType.Line, "bz_curve",
            params={"color1": hou.Vector4(1.0, 0.55, 0.0, 1.0), "line_width": 2.5})
        self.arms = hou.GeometryDrawable(sv, hou.drawableGeometryType.Line, "bz_arms",
            params={"color1": hou.Vector4(0.6, 0.8, 1.0, 1.0), "line_width": 1.0})
        self.pts = hou.GeometryDrawable(sv, hou.drawableGeometryType.Point, "bz_pts",
            params={"color1": hou.Vector4(1.0, 1.0, 1.0, 1.0), "radius": 6.0})
        self.drawables = (self.curve, self.arms, self.pts)

    # ---- helpers
    def _init_handles(self):
        init_handles(self.node)

    def _needs_init(self):
        n = self.node
        if not n.evalParm("custom_handles"):
            return True
        vals = [n.evalParmTuple(p) for p in ("start_pos", "handle1", "handle2", "end_pos")]
        return all(abs(c) < 1e-9 for v in vals for c in v)

    @staticmethod
    def _bez(a, b, c, d, t):
        u = 1.0 - t
        return a*(u*u*u) + b*(3*u*u*t) + c*(3*u*t*t) + d*(t*t*t)

    @staticmethod
    def _polyline(pts):
        g = hou.Geometry()
        ps = g.createPoints(pts)
        poly = g.createPolygon(is_closed=False)
        for p in ps:
            poly.addVertex(p)
        return g

    def _rebuild(self):
        solve = find_solve(self.node)
        if solve is None or solve.errors():
            return False
        P0, P1, P2, P3 = [hou.Vector3(read_detail_vec(solve, "bz_c%d" % i)) for i in range(4)]
        if P0 == P3:          # attribs missing (detail() returns 0) or degenerate
            return False

        N = 64
        self.curve.setGeometry(self._polyline([self._bez(P0, P1, P2, P3, i/float(N)) for i in range(N+1)]))
        arms = hou.Geometry()
        for a, b in ((P0, P1), (P3, P2)):
            ps = arms.createPoints([a, b])
            pr = arms.createPolygon(is_closed=False)
            pr.addVertex(ps[0]); pr.addVertex(ps[1])
        self.arms.setGeometry(arms)
        pg = hou.Geometry(); pg.createPoints([P0, P1, P2, P3])
        self.pts.setGeometry(pg)

        obj = self.node.parent()
        if isinstance(obj, hou.ObjNode):
            m = obj.worldTransform()
            for d in self.drawables:
                d.setTransform(m)
        return True

    # ---- events
    def onEnter(self, kwargs):
        self.node = kwargs["node"]
        if self._needs_init():
            self._init_handles()
        for d in self.drawables:
            d.show(True)

    def onExit(self, kwargs):
        for d in self.drawables:
            d.show(False)

    def onKeyEvent(self, kwargs):
        key = kwargs["ui_event"].device().keyString()
        if key == "r":
            self._init_handles()
            return True
        if key == "l":
            n = self.node
            locking = not n.evalParm("lock_ends")
            with hou.undos.group("Bezier: toggle lock ends"):
                if locking:   # snap end handles back onto the original points
                    solve = find_solve(n)
                    if solve is not None:
                        n.parmTuple("start_pos").set(read_detail_vec(solve, "bz_o0"))
                        n.parmTuple("end_pos").set(read_detail_vec(solve, "bz_o3"))
                n.parm("lock_ends").set(int(locking))
            return True
        return False

    def _sync_end_handles(self):
        locked = bool(self.node.evalParm("lock_ends"))
        if getattr(self, "_locked", None) == locked:
            return
        self._locked = locked
        for name in ("h0", "h3"):
            try:
                hou.Handle(self.scene_viewer, name).show(not locked)
            except hou.Error:
                pass

    def onDraw(self, kwargs):
        self._sync_end_handles()
        if self._rebuild():
            h = kwargs["draw_handle"]
            for d in self.drawables:
                d.draw(h)


def createViewerStateTemplate():
    state_typename = kwargs["type"].definition().sections()["DefaultState"].contents()
    t = hou.ViewerStateTemplate(state_typename, "Edge Bezier", hou.sopNodeTypeCategory())
    t.bindFactory(State)
    t.bindIcon(kwargs["type"].icon())
    t.bindHandleStatic("xform", "h0",
        [("start_posx", "tx"), ("start_posy", "ty"), ("start_posz", "tz")])
    t.bindHandleStatic("xform", "h3",
        [("end_posx", "tx"), ("end_posy", "ty"), ("end_posz", "tz")])
    t.bindHandleStatic("xform", "h1",
        [("handle1x", "tx"), ("handle1y", "ty"), ("handle1z", "tz")])
    t.bindHandleStatic("xform", "h2",
        [("handle2x", "tx"), ("handle2y", "ty"), ("handle2z", "tz")])
    return t
