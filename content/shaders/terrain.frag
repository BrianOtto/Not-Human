#version 330
//in float v_ao
in vec3 v_lit;
in vec2 v_uv;
//in float v_height;
//in vec3 v_world_pos;
uniform sampler2D texture0;
uniform sampler2D clrmap_grass;
uniform sampler2D clrmap_folage;
uniform sampler2D meta_atlas;
uniform sampler2D lightmap;
uniform vec3 fog_col;
uniform float chunk_fade;

// anim
uniform int  num_animated;
uniform vec4 adat[10];
uniform vec2 meta_szatlas;

out vec4 f_color;


float hash(vec2 p) {
    p = fract(p * vec2(123.34, 456.21));
    p += dot(p, p + 45.32);
    return fract(p.x * p.y);
}

float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}





vec3 lmap(vec2 bs) {
    return texture(lightmap, (bs + 0.5) / 16.0).rgb;
}

/*
// diffuse: n*sd remapped [0.3, 1.0]
float sunlight(vec3 n, vec3 sd) {
    float d = dot(normalize(n), normalize(sd)) * 0.35 + 0.65;
    return clamp(d, 0.3, 1.0);
}
*/

void main() {
    // anim: src uv -> meta atlas uv (adat = [src_uv, dst_uv])
    vec2 suv   = v_uv;
    bool anim  = false;
    float uv_w = 0.05;
    float uv_h  = 1.0 / 19.0;
    float eps   = 0.0001;

    for (int i = 0; i < num_animated && i < 10; i++) {
        vec2 diff = v_uv - adat[i].xy;
        if (diff.x >= -eps && diff.x <= uv_w + eps &&
            diff.y >= -eps && diff.y <= uv_h + eps) {
            float mtw = 16.0 / meta_szatlas.x;
            float mth = 16.0 / meta_szatlas.y;
            suv  = adat[i].zw + vec2(diff.x / uv_w * mtw, diff.y / uv_h * mth);
            anim = true;
            break;
        }
    }

    vec4 tc = anim ? texture(meta_atlas, suv) : texture(texture0, v_uv);
    if (tc.a < 0.1) discard;

    vec2 uv_g = vec2(0.3, 0.35);
    vec2 uv_f = vec2(0.4, 0.35);

    



    float r8b  = 1.0 - 9.0  * uv_h,  r8t  = 1.0 - 8.0  * uv_h;
    float r10b = 1.0 - 11.0 * uv_h,  r10t = 1.0 - 10.0 * uv_h;
    float r16b = 1.0 - 17.0 * uv_h,  r16t = 1.0 - 16.0 * uv_h;

    bool gtop  = v_uv.x >= 7.0*uv_w && v_uv.x < 8.0*uv_w && v_uv.y >= r8b && v_uv.y < r8t;
    bool gside = v_uv.x >= 4.0*uv_w && v_uv.x < 5.0*uv_w && v_uv.y >= r8b && v_uv.y < r8t;
    bool leaves = v_uv.y >= r10b && v_uv.y < r10t && v_uv.x >= 3.0*uv_w && v_uv.x < 9.0*uv_w;
    bool tgrs  = v_uv.x >= 8.0*uv_w && v_uv.x < 9.0*uv_w && v_uv.y >= r16b && v_uv.y < r16t;

    if (gtop || tgrs) {
        tc.rgb *= texture(clrmap_grass, uv_g).rgb;
    } else if (gside) {
        vec2 luv = vec2(
            fract((v_uv.x - 4.0 * uv_w) / uv_w),
            fract((v_uv.y - r8b) / uv_h)
        );
        vec4 ov = texture(texture0, vec2(5.0 * uv_w + luv.x * uv_w, r8b + luv.y * uv_h));
        if (ov.a > 0.1) tc.rgb = ov.rgb * texture(clrmap_grass, uv_g).rgb;
    } else if (leaves) {
        tc.rgb *= texture(clrmap_folage, uv_f).rgb;
    }

    

    if (v_uv.x >= 4.0*uv_w && v_uv.x < 7.0*uv_w && v_uv.y < uv_h)
        tc.rgb *= vec3(1.0, 0.2, 0.2);

    
    
    vec3 col = tc.rgb * lmap(v_lit.xy) * v_lit.z;

    // linear fog -> sky clr mix
    vec3  sky  = fog_col;
    float dist = gl_FragCoord.z / gl_FragCoord.w;
    float ff   = clamp((250.0 - dist) / 150.0, 0.0, 1.0);
    col = mix(sky, col, ff);
    col = mix(sky, col, chunk_fade);

    /*
    float ff = exp(-dist * 0.004);
    col = mix(sky, col, clamp(ff, 0.0, 1.0));
    */

    f_color = vec4(col, tc.a);
}
