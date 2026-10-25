
pipeline {
    agent any

    
environment {
    PYTHON_EXE = 'C:/Program Files/Python311/python.exe'
    PNPM_EXE = 'C:\\Users\\91979\\AppData\\Roaming\\npm\\pnpm.cmd'
}

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    stages {

        stage('Verify Environment') {
            steps {
                echo 'Engineering Drawing Review - CI'

                bat '''
                    @echo off
                    "%PYTHON_EXE%" --version
                    if errorlevel 1 exit /b 1

                    git --version
                    if errorlevel 1 exit /b 1
                '''
            }
        }

        stage('Create Python Environment') {
            steps {
                bat '''
                    "%PYTHON_EXE%" -m venv .venv
                    if errorlevel 1 exit /b 1
                '''
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
                    if errorlevel 1 exit /b 1
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
                    if errorlevel 1 exit /b 1
                '''
            }
        }

     
stage('Verify Frontend Tools') {
    steps {
        bat '''
            @echo off

            node --version
            if errorlevel 1 exit /b 1

            if not exist "%PNPM_EXE%" (
                echo ERROR: pnpm.cmd not found.
                exit /b 1
            )

            call "%PNPM_EXE%" --version
            if errorlevel 1 exit /b 1

            echo Frontend tools verified.
        '''
    }
}

stage('React Frontend Build') {
    steps {
        dir('frontend') {
            bat '''
                @echo off

                call "%PNPM_EXE%" install --frozen-lockfile
                if errorlevel 1 exit /b 1

                call "%PNPM_EXE%" run lint
                if errorlevel 1 exit /b 1

                call "%PNPM_EXE%" run build
                if errorlevel 1 exit /b 1

                echo React frontend build completed successfully.
            '''
        }
    }
}

    }

stage('Docker Image Build') {
    steps {
        bat '''
            @echo off

            docker --context desktop-linux info --format "{{.ServerVersion}}"
            if errorlevel 1 exit /b 1

            docker --context desktop-linux build ^
              -t drawing-review-tool:ci-%BUILD_NUMBER% ^
              .
            if errorlevel 1 exit /b 1

            echo Docker image built successfully.
        '''
    }
}

    post {
        always {
            junit(
                testResults: 'test-results.xml',
                allowEmptyResults: true
            )

            archiveArtifacts(
                artifacts: 'test-results.xml,frontend/dist/**',
                allowEmptyArchive: true,
                fingerprint: true
            )
        }

        success {
            echo 'Drawing Review CI: ALL STAGES PASSED!'
        }

        failure {
            echo 'Drawing Review CI: FAILURE - Review Console Output.'
        }
    }
}


