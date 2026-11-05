
// =========================================================
// CONTROLS
// =========================================================
int   curve_prim    = chi("curve_prim");

float u_start        = chf("u_start");
float u_end          = chf("u_end");
float slide_range    = chf("slide_range");     // how far the sub-segment travels as anim goes 0-1
int   arc_steps      = max(chi("arc_steps"), 64);  // arc-length lookup resolution

int   spread_seed    = chi("spread_seed");
int   spread_tries   = chi("spread_tries");

float radius_max        = chf("radius_max");
int   radius_seed       = chi("radius_seed");
float radius_falloff    = chf("radius_falloff");
float radius_ramp_amount = chf("radius_ramp_amount"); // max radius the whole-curve ramp can ADD
// radius_ramp  (chramp): along the whole curve (0 start .. 1 end) -> added radius

float angle_jitter   = chf("angle_jitter");
int   angle_seed     = chi("angle_seed");

float twist_amount   = chf("twist_amount");
float twist_anim     = chf("twist_anim");

float noise_amp       = chf("noise_amp");
float noise_freq      = chf("noise_freq");
float noise_time      = chf("noise_time");
int   noise_seed      = chi("noise_seed");
float noise_mix       = chf("noise_mix");

float spin_amount    = chf("spin_amount");
int   spin_seed      = chi("spin_seed");

float anim           = chf("anim");

float seek           = chf("seek");
float seek_window    = chf("seek_window");
int   seek_seed       = chi("seek_seed");
// seek_ramp  (chramp): curve position (0 start .. 1 end) -> extra seek


// =========================================================
// ARC-LENGTH reparameterisation — converts a normalised arc
// length s (0..1) into the curve's primuv U, so equal steps
// in s cover equal distance along the curve. This fixes the
// window "shrinking" caused by uneven curve parameterisation.
// =========================================================
float arcToU(int geo; int prim; float s; int steps)
{
    s = clamp(s, 0.0, 1.0);
    steps = max(steps, 2);

    // pass 1: total length of the curve
    float total = 0.0;
    vector prev = primuv(geo, "P", prim, set(0.0, 0.0, 0.0));
    for (int i = 1; i <= steps; i++) {
        vector p = primuv(geo, "P", prim, set(float(i) / float(steps), 0.0, 0.0));
        total += distance(p, prev);
        prev = p;
    }
    if (total <= 0.0)
        return s;

    // pass 2: walk to the target arc-length and interpolate U
    float target = s * total;
    float acc = 0.0;
    prev = primuv(geo, "P", prim, set(0.0, 0.0, 0.0));
    for (int i = 1; i <= steps; i++) {
        vector p = primuv(geo, "P", prim, set(float(i) / float(steps), 0.0, 0.0));
        float seg = distance(p, prev);
        if (acc + seg >= target) {
            float t = (target - acc) / max(seg, 1e-9);
            return (float(i - 1) + t) / float(steps);
        }
        acc += seg;
        prev = p;
    }
    return 1.0;
}


// =========================================================
// 0. cache target/final position (Input 0)
// =========================================================
vector targetPos = @P;

// =========================================================
// 1. DENSITY along sub-interval — rejection sampling vs spread_ramp
// =========================================================
// Computed first: u_local is the point's position within the window (0..1),
// needed by the slide step below.
float u_local = 0.5;
int   tries = max(spread_tries, 1);
for (int i = 0; i < tries; i++) {
    float candidate = rand(@ptnum * 17 + spread_seed + i * 971);
    float density    = chramp("spread_ramp", candidate);
    float accept      = rand(@ptnum * 31 + spread_seed + i * 733 + 500);
    u_local = candidate;
    if (accept < density)
        break;
}



// =========================================================
// 2. slide the window — constant *spatial* width, end never past the curve end
// =========================================================
// u_start / u_end are now normalised ARC-LENGTH positions (0..1),
// not raw primuv U. Working in arc length keeps the window the
// same real size no matter how unevenly the curve is parameterised.

float windowLen = u_end - u_start;   // window width in arc-length fraction (constant)

float offset = anim * slide_range;   // desired slide (anim 0..1 -> 0..slide_range)
offset = clamp(offset, -u_start, 1.0 - u_end);  // start >= 0 and end <= 1

float slideStart = u_start + offset;
float slideEnd   = slideStart + windowLen;      // derive end from start + fixed width

float s = fit(u_local, 0, 1, slideStart, slideEnd);  // arc-length position
float u = arcToU(1, curve_prim, s, arc_steps);       // -> primuv U for sampling


// =========================================================
// 3. curve frame at u
// =========================================================
vector curvePos = primuv(1, "P", curve_prim, set(u, 0, 0));

float du = 0.001;
vector p0 = primuv(1, "P", curve_prim, set(clamp(u - du, 0, 1), 0, 0));
vector p1 = primuv(1, "P", curve_prim, set(clamp(u + du, 0, 1), 0, 0));
vector tangent = normalize(p1 - p0);

vector worldup = set(0, 1, 0);
if (abs(dot(tangent, worldup)) > 0.99) worldup = set(1, 0, 0);
vector curveNormal = normalize(cross(worldup, tangent));


// =========================================================
// 4. TWIST — spiral angle as function of position along sub-segment + anim
// =========================================================
float spiralAngle = radians(twist_amount * u_local + twist_anim * anim);

float rseedA = rand(@ptnum + angle_seed) * 2 - 1;
float jitterAngle = rseedA * PI * angle_jitter;

float angle = spiralAngle + jitterAngle;
vector4 angleQ = quaternion(angle, tangent);
vector n_rot = qrotate(angleQ, curveNormal);


// =========================================================
// 5. RADIUS PROFILE — envelope shape away from curve
// =========================================================
float envelope = chramp("profile_ramp", u_local);
float curveRadius = chramp("radius_ramp", s);   // whole-curve ramp, sampled at absolute arc length
float rseedR = rand(@ptnum + radius_seed);
float radiusFrac = pow(rseedR, radius_falloff);
float radius = envelope * radius_max * radiusFrac + curveRadius * radius_ramp_amount;

vector radialOffset = n_rot * radius;
vector curvePosOffset = curvePos + radialOffset;


// =========================================================
// 6. SEEK — slider (staggered per point) + curve-position ramp
// =========================================================
float rseedSeek = rand(@ptnum + seek_seed);
float startT = rseedSeek * (1 - seek_window);
float endT   = startT + seek_window;
float sliderSeek = clamp(fit(seek, startT, endT, 0, 1), 0, 1);

// ramp along the curve: points near the curve end get pushed to seek.
// s is the absolute arc-length position (0 = curve start, 1 = curve end).
float rampSeek = chramp("seek_ramp", s);

float localSeek = max(sliderSeek, rampSeek);   // ramp can only raise the seek


// =========================================================
// 7. noise — fades per-point as seek progresses
// =========================================================
vector nOff = curlnoise(curvePosOffset * noise_freq + set(0, noise_time, 0) + noise_seed) * noise_amp;
vector curveStatePos = curvePosOffset + nOff * noise_mix * (1 - localSeek);

@P = lerp(curveStatePos, targetPos, localSeek); // exact @P at localSeek == 1


// =========================================================
// 8. orientation
// =========================================================
float rspin = rand(@ptnum + spin_seed) * 2 - 1;
float spinAngle = radians(spin_amount * rspin);
vector4 spinQ = quaternion(spinAngle, n_rot);

vector4 alignQ = dihedral(set(0, 1, 0), n_rot);
@orient = qmultiply(spinQ, alignQ);
@N = n_rot;
@up = tangent;


// =========================================================
// 9. COLLISION AVOIDANCE — push points outside an SDF (Input 2, VDB)
// =========================================================
int   sdf_avoid      = chi("sdf_avoid");       // toggle 0/1
int   sdf_prim        = chi("sdf_prim");        // usually 0
float sdf_offset      = chf("sdf_offset");      // safety margin — stay this far outside the surface
int   sdf_iterations  = chi("sdf_iterations");  // 2-4 usually enough for deep penetration
float sdf_strength    = chf("sdf_strength");    // 0-1, blend of correction applied

if (sdf_avoid) {
    for (int i = 0; i < sdf_iterations; i++) {
        float dist = volumesample(2, sdf_prim, @P);
        if (dist < sdf_offset) {
            vector grad = normalize(volumegradient(2, sdf_prim, @P));
            float pushAmt = (sdf_offset - dist) * sdf_strength;
            @P += grad * pushAmt;
        }
    }
}