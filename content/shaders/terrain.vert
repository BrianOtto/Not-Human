#version 330
in vec3 in_pos;
in vec3 in_lit;
in vec2 in_uv;
uniform mat4 mvp;
out vec3 v_lit;
out vec2 v_uv;
//out float v_height;
//out vec3 v_world_pos;


void main() {
    gl_Position = mvp * vec4(in_pos, 1.0);
    //v_normal = in_norm;
    v_lit = in_lit;
    v_uv = in_uv;
}
