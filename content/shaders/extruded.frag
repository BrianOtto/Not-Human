#version 330
in vec2 uv;
in vec3 normal;
out vec4 fragColor;
uniform sampler2D tex;
uniform vec3 tint;
uniform float ambient;


void main() {

    vec4 tc = texture(tex, uv);
    if (tc.a < 0.5) discard;
    vec3 n = normalize(normal);
    if (!gl_FrontFacing) n = -n;
    vec3 ldir = normalize(vec3(0.3, 1.0, 0.2));


    // diff: n*ldir, mixed [ambient, 1.0]
    float diff = max(0.4, dot(n, ldir));
    float lit  = mix(ambient, 1.0, diff);
    fragColor = vec4(tc.rgb * tint * lit, tc.a);
}
