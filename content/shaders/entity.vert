#version 330
in vec3 in_pos;
in vec2 in_uv;
in vec3 in_norm;
in float in_part_id;

uniform mat4 mvp;
uniform vec3 ent_pos;
uniform float ent_yaw;
uniform mat4 parts[12];
uniform float hidepart;   // -1 all

out vec2 v_uv;
out vec3 v_normal;
out vec3 v_world_pos;





void main() {
    int  pid = int(in_part_id + 0.5);
    mat4 m   = parts[pid];

    vec3 pos  = (m * vec4(in_pos, 1.0)).xyz;
    vec3 norm = mat3(m) * in_norm;


    // R_y(yaw -90) -> world space
    float yr = radians(ent_yaw - 90.0);
    float cy = cos(yr), sy = sin(yr);

    vec3 rpos  = vec3(pos.x*cy - pos.z*sy, pos.y, pos.x*sy + pos.z*cy);
    vec3 rnorm = vec3(norm.x*cy - norm.z*sy, norm.y, norm.x*sy + norm.z*cy);

    v_normal = rnorm;


    

    if (hidepart > -0.5 && abs(float(pid) - hidepart) < 0.5) {
        gl_Position = vec4(0.0, 0.0, -10.0, 1.0);
        v_uv        = in_uv;
        v_world_pos = vec3(0.0);
    } else {
        vec3 wp     = rpos + ent_pos;
        gl_Position = mvp * vec4(wp, 1.0);
        v_uv        = in_uv;
        v_world_pos = wp;
    }
}
