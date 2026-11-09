
const REDIRECT_URI =
  "https://fortaleza-youtube-auth.z44d2z597w.workers.dev/callback";

const MAX_VIDEO_SIZE = 90 * 1024 * 1024;

function reply(message, status = 200, headers = {}) {
  return new Response(message, {
    status,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "no-store",
      ...headers
    }
  });
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store"
    }
  });
}

function getConfig(env) {
  return {
    clientId:
      typeof env.GOOGLE_CLIENT_ID === "string"
        ? env.GOOGLE_CLIENT_ID.trim()
        : "",
    clientSecret:
      typeof env.GOOGLE_CLIENT_SECRET === "string"
        ? env.GOOGLE_CLIENT_SECRET.trim()
        : "",
    uploadKey:
      typeof env.FORTALEZA_UPLOAD_KEY === "string"
        ? env.FORTALEZA_UPLOAD_KEY.trim()
        : ""
  };
}

function safeEqual(a, b) {
  if (!a || !b || a.length !== b.length) return false;

  let result = 0;

  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }

  return result === 0;
}

async function getYouTubeAccessToken(env, config) {
  const refreshToken = await env.YOUTUBE_TOKENS.get(
    "youtube_refresh_token"
  );

  if (!refreshToken) {
    throw new Error("No existe un token de YouTube guardado.");
  }

  const response = await fetch(
    "https://oauth2.googleapis.com/token",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded"
      },
      body: new URLSearchParams({
        client_id: config.clientId,
        client_secret: config.clientSecret,
        refresh_token: refreshToken,
        grant_type: "refresh_token"
      })
    }
  );

  const data = await response.json();

  if (!response.ok || !data.access_token) {
    throw new Error(
      data.error_description || data.error || "No se pudo renovar el acceso."
    );
  }

  return data.access_token;
}

async function publicarVideo(request, env, config) {
  if (!config.uploadKey) {
    return json({ error: "Falta configurar FORTALEZA_UPLOAD_KEY." }, 500);
  }

  const receivedKey = request.headers.get("X-Fortaleza-Key") || "";

  if (!safeEqual(receivedKey, config.uploadKey)) {
    return json({ error: "Acceso no autorizado." }, 401);
  }

  if (!config.clientId || !config.clientSecret || !env.YOUTUBE_TOKENS) {
    return json({ error: "La configuración de YouTube está incompleta." }, 500);
  }

  const contentType = request.headers.get("Content-Type") || "";

  if (!contentType.toLowerCase().startsWith("video/mp4")) {
    return json({ error: "El archivo debe ser un video MP4." }, 415);
  }

  const size = Number(request.headers.get("Content-Length") || 0);

  if (!Number.isSafeInteger(size) || size <= 0 || size > MAX_VIDEO_SIZE) {
    return json({
      error: "Tamaño de video inválido. El límite configurado es 90 MB."
    }, 413);
  }

  const title = (request.headers.get("X-Video-Title") || "").trim();
  const description =
    (request.headers.get("X-Video-Description") || "").trim();

  if (!title || title.length > 100) {
    return json({ error: "El título es obligatorio y admite hasta 100 caracteres." }, 400);
  }

  if (description.length > 5000) {
    return json({ error: "La descripción supera los 5000 caracteres." }, 400);
  }

  if (!request.body) {
    return json({ error: "No se recibió el archivo de video." }, 400);
  }

  try {
    const accessToken = await getYouTubeAccessToken(env, config);

    const metadata = {
      snippet: {
        title,
        description,
        defaultLanguage: "es-MX",
        defaultAudioLanguage: "es-MX"
      },
      status: {
        privacyStatus: "public"
      }
    };

    const startUpload = await fetch(
      "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json; charset=UTF-8",
          "X-Upload-Content-Type": "video/mp4",
          "X-Upload-Content-Length": String(size)
        },
        body: JSON.stringify(metadata)
      }
    );

    if (!startUpload.ok) {
      const errorText = await startUpload.text();

      return json({
        error: "YouTube rechazó el inicio de la publicación.",
        details: errorText.slice(0, 2000)
      }, 502);
    }

    const uploadUrl = startUpload.headers.get("Location");

    if (!uploadUrl) {
      return json({
        error: "YouTube no entregó la dirección de carga."
      }, 502);
    }

    const uploadResponse = await fetch(uploadUrl, {
      method: "PUT",
      headers: {
        "Content-Type": "video/mp4",
        "Content-Length": String(size)
      },
      body: request.body
    });

    const resultText = await uploadResponse.text();

    let result;

    try {
      result = JSON.parse(resultText);
    } catch {
      result = { details: resultText.slice(0, 2000) };
    }

    if (!uploadResponse.ok) {
      return json({
        error: "YouTube no pudo completar la publicación.",
        details: result
      }, 502);
    }

    return json({
      success: true,
      message: "Video enviado correctamente a YouTube.",
      video_id: result.id,
      title: result.snippet?.title || title,
      url: result.id
        ? `https://www.youtube.com/watch?v=${result.id}`
        : null
    });

  } catch (error) {
    return json({
      error: "Error durante la publicación.",
      details: error.message
    }, 500);
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const { clientId, clientSecret, uploadKey } = getConfig(env);

    // Publicación automática: POST /publicar
    if (url.pathname === "/publicar") {
      if (request.method !== "POST") {
        return reply("Utiliza POST para publicar un video.", 405);
      }

      return publicarVideo(request, env, {
        clientId,
        clientSecret,
        uploadKey
      });
    }

    if (request.method !== "GET") {
      return reply("Método no permitido.", 405);
    }

    // Página principal
    if (url.pathname === "/") {
      return reply(
        "FORTALEZA MEDIA AI: servidor de autorizacion activo."
      );
    }

    // Diagnóstico seguro
    if (url.pathname === "/diagnostico") {
      return json({
        worker: "FORTALEZA MEDIA AI",
        client_id: clientId,
        client_id_configured: Boolean(clientId),
        client_id_length: clientId.length,
        client_id_format:
          clientId.endsWith(".apps.googleusercontent.com"),
        client_secret_configured: Boolean(clientSecret),
        upload_key_configured: Boolean(uploadKey),
        kv_configured: Boolean(env.YOUTUBE_TOKENS),
        redirect_uri: REDIRECT_URI
      });
    }

    // Inicio de autorización de Google
    if (url.pathname === "/login") {
      if (!clientId || !clientSecret || !env.YOUTUBE_TOKENS) {
        return reply(
          "Falta configurar GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET o YOUTUBE_TOKENS.",
          500
        );
      }

      const state = crypto.randomUUID();

      await env.YOUTUBE_TOKENS.put(
        `oauth_state:${state}`,
        "valid",
        { expirationTtl: 600 }
      );

      const googleURL = new URL(
        "https://accounts.google.com/o/oauth2/v2/auth"
      );

      googleURL.searchParams.set("client_id", clientId);
      googleURL.searchParams.set("redirect_uri", REDIRECT_URI);
      googleURL.searchParams.set("response_type", "code");
      googleURL.searchParams.set(
        "scope",
        "https://www.googleapis.com/auth/youtube.upload"
      );
      googleURL.searchParams.set("access_type", "offline");
      googleURL.searchParams.set("prompt", "consent");
      googleURL.searchParams.set("state", state);

      return new Response(null, {
        status: 302,
        headers: {
          Location: googleURL.toString(),
          "Set-Cookie":
            `fortaleza_oauth_state=${state}; HttpOnly; Secure; SameSite=Lax; Path=/callback; Max-Age=600`
        }
      });
    }

    // Respuesta de Google
    if (url.pathname === "/callback") {
      const error = url.searchParams.get("error");

      if (error) {
        return reply(
          "Google no completó la autorización: " + error,
          400
        );
      }

      const code = url.searchParams.get("code");
      const state = url.searchParams.get("state");

      const cookie = request.headers.get("Cookie") || "";
      const match = cookie.match(
        /(?:^|;\s*)fortaleza_oauth_state=([^;]+)/
      );

      const cookieState = match ? match[1] : "";

      const clearCookie =
        "fortaleza_oauth_state=; HttpOnly; Secure; SameSite=Lax; Path=/callback; Max-Age=0";

      if (!code || !state || state !== cookieState) {
        return reply(
          "Falló la validación de seguridad. Vuelve a iniciar desde /login.",
          400,
          { "Set-Cookie": clearCookie }
        );
      }

      if (!clientId || !clientSecret || !env.YOUTUBE_TOKENS) {
        return reply(
          "Falta configurar las credenciales o KV.",
          500,
          { "Set-Cookie": clearCookie }
        );
      }

      const stateKey = `oauth_state:${state}`;
      const savedState = await env.YOUTUBE_TOKENS.get(stateKey);

      if (!savedState) {
        return reply(
          "La solicitud expiró o ya fue utilizada. Vuelve a iniciar desde /login.",
          403,
          { "Set-Cookie": clearCookie }
        );
      }

      await env.YOUTUBE_TOKENS.delete(stateKey);

      const tokenResponse = await fetch(
        "https://oauth2.googleapis.com/token",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded"
          },
          body: new URLSearchParams({
            code,
            client_id: clientId,
            client_secret: clientSecret,
            redirect_uri: REDIRECT_URI,
            grant_type: "authorization_code"
          })
        }
      );

      let tokens;

      try {
        tokens = await tokenResponse.json();
      } catch {
        return reply(
          "Google devolvió una respuesta que no se pudo interpretar.",
          502,
          { "Set-Cookie": clearCookie }
        );
      }

      if (!tokenResponse.ok) {
        return reply(
          "Error de Google: " +
            (tokens.error_description || tokens.error || "desconocido"),
          400,
          { "Set-Cookie": clearCookie }
        );
      }

      if (!tokens.refresh_token) {
        return reply(
          "Google no entregó un refresh token. Revisa el consentimiento OAuth.",
          400,
          { "Set-Cookie": clearCookie }
        );
      }

      await env.YOUTUBE_TOKENS.put(
        "youtube_refresh_token",
        tokens.refresh_token
      );

      return reply(
        "FORTALEZA MEDIA AI: autorización de YouTube completada. Token guardado.",
        200,
        { "Set-Cookie": clearCookie }
      );
    }

    return reply("Ruta no encontrada.", 404);
  }
};
