#version 330
in vec3 v_world_pos;
in vec4 v_clip_pos;
uniform sampler2D depth_texture;
uniform mat4 proj;
uniform float near;
uniform float far;
out vec4 f_color;

// l/d linearized depth from ndc z
float lindepth(float depth) {
    float z = depth * 2.0 - 1.0;
    return (2.0 * near * far) / (far + near - z * (far - near));
}

void main() {
    
    vec2 sp  = (v_clip_pos.xy / v_clip_pos.w) * 0.5 + 0.5;
    float lsd = lindepth(texture(depth_texture, sp).r);
    float lwd = lindepth(gl_FragCoord.z);
    float dd  = lsd - lwd;

    // ea/eb/ec = foam bands at 3 scales
    float ea = pow(1.0 - smoothstep(0.0, 1.225, dd), 3.0);
    float eb = pow(1.0 - smoothstep(0.0, 2.275, dd), 2.0);
    float ec = pow(1.0 - smoothstep(0.0, 3.5,   dd), 1.5);

    
    float wf = max(ea, max(eb * 0.6, ec * 0.3));

    
    vec3 dw = vec3(0.05, 0.25, 0.65);
    vec3 sw = vec3(0.15, 0.45, 0.85);
    vec3 wc = mix(dw, sw, ec * 0.4);
    if (wf > 0.1) wc = mix(wc, vec3(1.0), wf * wf);

    // linear fog -> sky clr mix
    float dist = gl_FragCoord.z / gl_FragCoord.w;
    float ff   = clamp((250.0 - dist) / 150.0, 0.0, 1.0);
    vec3 skyc  = vec3(0.529, 0.808, 0.922);

    f_color = vec4(mix(skyc, wc, ff), mix(0.8, 0.95, wf));
}
