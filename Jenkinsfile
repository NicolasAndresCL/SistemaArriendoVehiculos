// Pipeline declarativo del Sistema de Arriendo de Vehículos.
//
// Alternativa on-prem al workflow de GitHub Actions (.github/workflows/ci.yml).
// Mantiene el mismo filtro de calidad: verifica que el proyecto CONSTRUYE y
// ARRANCA, no solo que pasa un linter. Los stages van de rápido a lento, para
// no gastar minutos de agente en un build que ruff iba a rechazar en segundos.

pipeline {
    // Agente Docker efímero: el build de hoy corre en el mismo entorno limpio
    // que el de mañana. Un agente persistente acumula estado y produce el
    // clásico "funciona en mi agente".
    // Misma versión que el CI de GitHub Actions y que el Dockerfile.
    agent {
        docker { image 'python:3.13-slim' }
    }

    options {
        timeout(time: 20, unit: 'MINUTES')   // ningún job cuelga para siempre
        disableConcurrentBuilds()            // dos builds sobre la misma base de test se corrompen
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    environment {
        PIP_NO_CACHE_DIR = '1'
        PYTHONUNBUFFERED = '1'
        // Ninguna credencial en claro aquí: el Jenkinsfile vive en el repo,
        // así que cualquier secreto escrito acá es un secreto filtrado.
    }

    stages {
        stage('Dependencias') {
            steps {
                sh 'python -m venv /tmp/venv'
                sh '/tmp/venv/bin/pip install --upgrade pip'
                sh '/tmp/venv/bin/pip install -r requirements-dev.txt'
            }
        }

        stage('Lint y formato') {
            steps {
                sh '/tmp/venv/bin/ruff check .'
                sh '/tmp/venv/bin/ruff format --check .'
            }
        }

        stage('Tests y cobertura') {
            steps {
                // -ra: un test saltado en silencio debe verse en el log,
                // no pasar inadvertido.
                sh '''/tmp/venv/bin/pytest -ra \
                        --cov --cov-report=term-missing \
                        --cov-report=xml:coverage.xml \
                        --junitxml=test-results/junit.xml \
                        --cov-fail-under=80'''
            }
        }

        stage('Hardening de producción') {
            steps {
                // Sin una SECRET_KEY fuerte, `check --deploy` falla por la
                // clave débil y no por el hardening real, que es lo que este
                // stage quiere verificar.
                sh '''export SECRET_KEY="$(/tmp/venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(64))')"
                      export DJANGO_SETTINGS_MODULE=config.settings.prod
                      export ALLOWED_HOSTS=arriendos.example.cl
                      export SECURE_HTTPS=True
                      export DATABASE_URL=sqlite:///db-check.sqlite3
                      /tmp/venv/bin/python backend/manage.py check --deploy --fail-level WARNING'''
            }
        }

        stage('Build de imagen') {
            when { branch 'main' }
            // El build de imagen necesita el demonio de Docker del host, no el
            // agente Python de los stages anteriores.
            agent any
            steps {
                script {
                    def imagen = "sistema-arriendo:${env.GIT_COMMIT.take(7)}"
                    sh "docker build -t ${imagen} ."
                    // Tag inmutable por commit: nunca `latest`, o dos réplicas
                    // podrían acabar corriendo código distinto.
                    sh "docker image inspect ${imagen} >/dev/null"
                }
            }
        }

        stage('Despliegue') {
            when { branch 'main' }
            agent any
            steps {
                // Las credenciales salen del credential store de Jenkins,
                // nunca del Jenkinsfile ni de variables globales del job.
                withCredentials([file(credentialsId: 'kubeconfig-arriendos', variable: 'KUBECONFIG')]) {
                    sh "kubectl apply -k deploy/k8s/"
                    // Migraciones como Job aparte, antes de rotar las réplicas.
                    sh "kubectl wait --for=condition=complete job/migraciones --timeout=180s"
                    // `rollout status` hace fallar el build si el despliegue no
                    // converge, en vez de dar por bueno un `apply` que aceptó
                    // el manifiesto pero dejó los pods en CrashLoopBackOff.
                    sh "kubectl rollout status deployment/backend --timeout=180s"
                    sh "kubectl rollout status deployment/frontend --timeout=180s"
                }
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'test-results/*.xml'
        }
        failure {
            echo "Build fallido en el stage '${env.STAGE_NAME}'. Revisar ese log antes de reintentar: un reintento a ciegas repite el mismo fallo."
        }
    }
}
