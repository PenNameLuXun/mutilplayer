#version 330 core
in vec2 vTexCoord;
out vec4 FragColor;

uniform sampler2D tex;
uniform vec2 videoSize;
uniform vec2 widgetSize;

void main() {
    float videoAspect = videoSize.x / videoSize.y;
    float widgetAspect = widgetSize.x / widgetSize.y;

    vec2 uv = vTexCoord;

    if (videoAspect > widgetAspect) {
        float scale = widgetAspect / videoAspect;
        uv.y = (uv.y - 0.5) / scale + 0.5;
    } else {
        float scale = videoAspect / widgetAspect;
        uv.x = (uv.x - 0.5) / scale + 0.5;
    }

    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0)
        FragColor = vec4(0, 0, 0, 1);
    else
        FragColor = texture(tex, uv);
}
