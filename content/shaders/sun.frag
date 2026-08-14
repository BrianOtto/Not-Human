#version 330
in vec2 v_offset;
out vec4 f_color;
void main() {
    // r = |offset| from billboard center
    float r = length(v_offset);
    if (r > 1.0) discard;

    float rad  = 0.3;
    // core
    float core = 1.0 - smoothstep(rad, rad + 0.02, r);
    float glow = max(exp(-r * 4.0) * 0.7, exp(-r * 2.0) * 0.2);

    
    vec3 cc = vec3(1.0, 1.0, 0.9);
    vec3 gc = vec3(1.0, 0.7, 0.3);

    vec3 color = mix(gc, cc, core);
    color += gc * glow * 0.8;

    float ba = clamp(smoothstep(0.0, 1.0, glow) * 1.5, 0.0, 1.0);
    float alpha = max(core, ba) * (1.0 - smoothstep(0.9, 1.0, r));

    f_color = vec4(color, alpha);
}
