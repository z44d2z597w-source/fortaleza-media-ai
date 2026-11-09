
const REDIRECT_URI =
  "https://fortaleza-youtube-auth.z44d2z597w.workers.dev/callback";

function reply(message, status = 200, headers = {}) {
  return new Response(message, {
    status,
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      ...headers
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
        : ""
  };
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method !== "GET") {
      return reply("Método no permitido.", 405);
    }

    const { clientId, clientSecret } = getConfig(env);

    // Página principal
    if (url.pathname === "/") {
      return reply(
        "FORTALEZA MEDIA AI: servidor de autorizacion activo."
      );
    }

    // Diagnóstico seguro: nunca muestra el secreto
    if (url.pathname === "/diagnostico") {
      return new Response(
        JSON.stringify(
          {
            worker: "FORTALEZA MEDIA AI",
            client_id: clientId,
            client_id_configured: Boolean(clientId),
            client_id_length: clientId.length,
            client_id_format:
              clientId.endsWith(".apps.googleusercontent.com"),
            client_secret_configured: Boolean(clientSecret),
            kv_configured: Boolean(env.YOUTUBE_TOKENS),
            redirect_uri: REDIRECT_URI
          },
          null,
          2
        ),
        {
          headers: {
            "Content-Type": "application/json; charset=utf-8",
            "Cache-Control": "no-store"
          }
        }
      );
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
