# Contrato de salida del módulo: lo que el pipeline necesita para desplegar.

output "namespace" {
  description = "Namespace creado, para el `kubectl apply -k` posterior."
  value       = kubernetes_namespace.arriendos.metadata[0].name
}

output "url_publica" {
  description = "URL pública del sistema una vez desplegado."
  value       = "https://${var.host_publico}"
}

output "nombre_secreto" {
  description = "Nombre del Secret que consumen los Deployments."
  value       = kubernetes_secret.arriendos.metadata[0].name
}

output "secret_key" {
  description = "Clave de firma de Django generada para este entorno."
  value       = random_password.secret_key.result
  # `sensitive` evita que el valor se imprima en el log del plan, que en CI
  # lee todo el equipo. NO cifra el estado: ahí sigue en claro.
  sensitive = true
}
