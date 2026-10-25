
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

stage('Prepare Test Drawings') {
    steps {
        bat '''
            @echo off
            set "SOURCE=E:\\AI-Workspace\\projects\\Engineering-Drawing-PoC\\data\\input"
            set "DEST=data\\input"

            if not exist "%SOURCE%\\" (
                echo ERROR: Approved test data folder not found.
                exit /b 1
            )

            if not exist "%DEST%" mkdir "%DEST%"

            for %%F in (
                47789413_C_watermarked.pdf
                47789460_B_watermarked.pdf
                47789660_A_watermarked.pdf
            ) do (
                if not exist "%SOURCE%\\%%F" (
                    echo ERROR: Missing test fixture %%F
                    exit /b 1
                )
                copy /Y "%SOURCE%\\%%F" "%DEST%\\%%F" >nul
                if errorlevel 1 exit /b 1
            )

            echo Approved test fixtures prepared successfully.
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
    stage('React Frontend Build') {
    steps {
        bat '''
            cd frontend
            call pnpm install --frozen-lockfile
            if errorlevel 1 exit /b 1

            call pnpm run lint
            if errorlevel 1 exit /b 1

            call pnpm run build
            if errorlevel 1 exit /b 1
        '''
    }
}

