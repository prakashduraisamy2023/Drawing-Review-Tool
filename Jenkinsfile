
pipeline {
    agent any

    environment {
        PYTHON_EXE = 'C:/Program Files/Python311/python.exe'
    }

    stages {
        stage('Verify Environment') {
            steps {
                echo 'Engineering Drawing Review - CI'
                bat '"%PYTHON_EXE%" --version'
                bat 'git --version'
            }
        }

        stage('Create Python Environment') {
            steps {
                bat '"%PYTHON_EXE%" -m venv .venv'
            }
        }

        stage('Install Dependencies') {
            steps {
                bat '''
                    ".venv\\Scripts\\python.exe" -m pip install -r backend\\requirements-dev.txt
                    if errorlevel 1 exit /b 1

                    ".venv\\Scripts\\python.exe" -m pip install -r requirements.txt
                    if errorlevel 1 exit /b 1
                '''
            }
        }

        stage('Python Code Quality') {
            steps {
                bat '''
                    ".venv\\Scripts\\python.exe" -m ruff check backend tests scripts
                '''
            }
        }

        stage('Automated Tests') {
            steps {
                bat '''
                    ".venv\\Scripts\\python.exe" -m pytest tests -q --junitxml=test-results.xml
                '''
            }
        }
    }

    post {
        always {
            junit(
                testResults: 'test-results.xml',
                allowEmptyResults: true
            )
            archiveArtifacts(
                artifacts: 'test-results.xml',
                allowEmptyArchive: true
            )
        }

        success {
            echo 'Drawing Review CI: SUCCESS!'
        }

        failure {
            echo 'Drawing Review CI: FAILURE - Check console output.'
        }
    }
}
