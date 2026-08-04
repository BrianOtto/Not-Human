#version 330
in vec2 v_uv;
in vec3 v_normal;
in vec3 v_world_pos;
uniform sampler2D skin_texture;
uniform vec3 sun_pos;
uniform float hurt;
out vec4 f_color;

void main() {
    if (length(v_world_pos) < 0.001) discard;

    vec4 tex = texture(skin_texture, v_uv);
    if (tex.a < 0.1) discard;

    vec3 n = normalize(v_normal);
    // face shade: n·y -> brightness, mc-style
    float br;
    if      (n.y >  0.5)      br = 1.0;
    else if (n.y < -0.5)      br = 0.5;
    else if (abs(n.z) > 0.5)  br = 0.8;
    else if (abs(n.x) > 0.5)  br = 0.6;
    else                      br = 0.8;

    // diffuse: n*sd remapped [0.4, 1.0]
    vec3 sd = normalize(sun_pos);
    float sl = clamp(dot(n, sd) * 0.4 + 0.6, 0.4, 1.0);

    vec3 color = tex.rgb * (br * sl);
    color = mix(color, vec3(1.0, 0.0, 0.0), hurt * 0.5);

    // linear fog -> sky color mix
    float dist = gl_FragCoord.z / gl_FragCoord.w;
    float f0 = 100.0, f1 = 250.0;
    float ff = clamp((f1 - dist) / (f1 - f0), 0.0, 1.0);
    vec3 skyc = vec3(0.529, 0.808, 0.922);
    color = mix(skyc, color, ff);

    f_color = vec4(color, tex.a);
}
