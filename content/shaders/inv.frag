#version 330
in vec2 v_uv;
in vec3 v_normal;
uniform sampler2D skin_texture;
out vec4 f_color;

void main() {
    vec4 tex = texture(skin_texture, v_uv);
    if (tex.a < 0.1) discard;

    vec3 n = normalize(v_normal);
    // face shade: n*y -> br, mc-style
    float br;
    if      (n.y >  0.5)      br = 1.0;
    else if (n.y < -0.5)      br = 0.5;
    else if (abs(n.z) > 0.5)  br = 0.8;
    else if (abs(n.x) > 0.5)  br = 0.6;
    else                      br = 0.8;

    f_color = vec4(tex.rgb * (br * 0.9 + 0.1), tex.a);
}
