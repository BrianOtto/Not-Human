#version 330

uniform sampler2D texture0;
uniform vec3 sun_dir;

in vec2 v_uv;
in vec3 v_normal;
in vec3 v_frag_pos;
in vec3 v_tint;

out vec4 f_color;

void main() {
    vec4 tex = texture(texture0, v_uv);
    if (tex.a < 0.5) discard;

    vec3 tinted = tex.rgb * v_tint;
    vec3 n = normalize(v_normal);
    if (!gl_FrontFacing) n = -n;

    // diff: n*sun_dir -> lit [0.4, 1.0]
    float diff = max(dot(n, normalize(sun_dir)), 0.0);
    float lit  = 0.4 + diff * 0.6;

    f_color = vec4(tinted * lit, tex.a);
}
