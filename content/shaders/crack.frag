#version 330

uniform sampler2D texture0;
uniform vec2 uv0;
uniform vec2 uvsz;

in vec2 v_uv;
out vec4 f_color;

void main() {
    vec4 t = texture(texture0, uv0 + v_uv * uvsz);
    if (t.a < 0.05) discard;
    f_color = t;
}
