#version 330
in vec2 v_uv;
uniform sampler2D tex;
uniform vec4 tint; 
out vec4 f_color;

void main() {
    vec4 color = texture(tex, v_uv);
    if (color.a < 0.01) discard;
    color *= tint;
    if (color.a < 0.01) discard;
    f_color = color;
}
