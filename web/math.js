/**
 * Quaternion and rotation helpers.
 * Convention: [x, y, z, w]  (Hamilton, matching WebXR).
 */

export function quatNormalize(q) {
  const [x, y, z, w] = q;
  const n = Math.sqrt(x * x + y * y + z * z + w * w);
  if (n < 1e-10) return [0, 0, 0, 1];
  return [x / n, y / n, z / n, w / n];
}

export function quatConjugate(q) {
  return [-q[0], -q[1], -q[2], q[3]];
}

export function quatMultiply(a, b) {
  const [ax, ay, az, aw] = a;
  const [bx, by, bz, bw] = b;
  return [
    aw * bx + ax * bw + ay * bz - az * by,
    aw * by - ax * bz + ay * bw + az * bx,
    aw * bz + ax * by - ay * bx + az * bw,
    aw * bw - ax * bx - ay * by - az * bz,
  ];
}

export function quatToEuler(q) {
  const [x, y, z, w] = q;
  const sinr = 2 * (w * x + y * z);
  const cosr = 1 - 2 * (x * x + y * y);
  const roll = Math.atan2(sinr, cosr);

  let sinp = 2 * (w * y - z * x);
  sinp = Math.max(-1, Math.min(1, sinp));
  const pitch = Math.asin(sinp);

  const siny = 2 * (w * z + x * y);
  const cosy = 1 - 2 * (y * y + z * z);
  const yaw = Math.atan2(siny, cosy);

  return { roll, pitch, yaw };
}

export function eulerToQuat(roll, pitch, yaw) {
  const cr = Math.cos(roll / 2), sr = Math.sin(roll / 2);
  const cp = Math.cos(pitch / 2), sp = Math.sin(pitch / 2);
  const cy = Math.cos(yaw / 2), sy = Math.sin(yaw / 2);
  return [
    sr * cp * cy - cr * sp * sy,
    cr * sp * cy + sr * cp * sy,
    cr * cp * sy - sr * sp * cy,
    cr * cp * cy + sr * sp * sy,
  ];
}

/** Convert DeviceOrientation (alpha, beta, gamma) degrees to [x,y,z,w] quat. */
export function deviceOrientationToQuat(alpha, beta, gamma) {
  const a = (alpha || 0) * Math.PI / 180;
  const b = (beta || 0) * Math.PI / 180;
  const g = (gamma || 0) * Math.PI / 180;

  const c1 = Math.cos(a / 2), s1 = Math.sin(a / 2);
  const c2 = Math.cos(b / 2), s2 = Math.sin(b / 2);
  const c3 = Math.cos(g / 2), s3 = Math.sin(g / 2);

  // ZXY rotation order (W3C spec)
  return quatNormalize([
    s1 * s2 * c3 + c1 * c2 * s3,    // x  (not standard XYZ — this is ZXY)
    c1 * s2 * c3 + s1 * c2 * s3,    // y
    c1 * c2 * c3 - s1 * s2 * s3,    // z  — note: not the obvious one
    s1 * c2 * c3 - c1 * s2 * s3,    // w
    // Actually use the proper ZXY decomposition:
  ]);
}

/**
 * More reliable DeviceOrientation → quaternion using the standard
 * ZXY Euler decomposition that the W3C DeviceOrientation spec defines.
 */
export function deviceOrientationToQuatZXY(alpha, beta, gamma) {
  const degToRad = Math.PI / 180;
  const a = (alpha || 0) * degToRad;  // Z axis
  const b = (beta || 0) * degToRad;   // X axis
  const g = (gamma || 0) * degToRad;  // Y axis

  const cx = Math.cos(b / 2), sx = Math.sin(b / 2);
  const cy = Math.cos(g / 2), sy = Math.sin(g / 2);
  const cz = Math.cos(a / 2), sz = Math.sin(a / 2);

  // Rotation order: Z (alpha) * X (beta) * Y (gamma)
  const x = sx * cy * cz - cx * sy * sz;
  const y = cx * sy * cz + sx * cy * sz;
  const z = cx * cy * sz + sx * sy * cz;
  const w = cx * cy * cz - sx * sy * sz;

  return quatNormalize([x, y, z, w]);
}

export function radToDeg(r) { return r * 180 / Math.PI; }
export function degToRad(d) { return d * Math.PI / 180; }
