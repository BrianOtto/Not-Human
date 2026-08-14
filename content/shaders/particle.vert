#version 330
in vec3 in_pos;
in vec2 in_offset;
in vec2 in_uv;
in float in_alpha;
in float in_size;
in vec3 in_tint;

uniform mat4 mvp;
uniform vec3 cam_r;
uniform vec3 cam_u;

out vec2 v_uv;
out float v_alpha;
out vec3 v_tint;

void main() {
    vec3 world_pos = in_pos
        + cam_r * in_offset.x * in_size
        + cam_u * in_offset.y * in_size;

    gl_Position = mvp * vec4(world_pos, 1.0);
    v_uv = in_uv;
    v_alpha = in_alpha;
    v_tint = in_tint;
}
