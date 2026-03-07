// Dashboard для тестирования
let currentTest = null;
let testResults = [];

// Глобальные функции для тестов
window.runQuickTest = runQuickTest;
window.runFullTest = runFullTest;
window.runStressTest = runStressTest;
window.runAllTests = runAllTests;
window.clearLogs = clearLogs;

// Запуск быстрого теста
async function runQuickTest() {
    if (currentTest) {
        addTestLog('Тест уже запущен', 'warning');
        return;
    }
    
    addTestLog('🚀 Запуск быстрого теста...', 'info');
    updateTestStatus('Выполняется быстрый тест...');
    currentTest = 'quick';
    
    try {
        const response = await fetch('/api/test/quick', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            addTestLog(`✅ Быстрый тест завершен: ${result.score || 'N/A'}%`, 'success');
            
            // Добавляем дополнительную информацию
            if (result.nodes_started !== undefined) {
                addTestLog(`📊 Узлов запущено: ${result.nodes_started}`, 'info');
            }
            if (result.test_completed !== undefined) {
                addTestLog(`🎯 Тест завершен: ${result.test_completed ? 'Да' : 'Нет'}`, 'info');
            }
            
            updateTestResults({
                type: 'quick',
                score: result.score || 0,
                duration: result.duration || 0,
                status: 'completed',
                nodes_started: result.nodes_started,
                test_completed: result.test_completed
            });
        } else {
            addTestLog(`❌ Ошибка быстрого теста: ${result.error}`, 'error');
            updateTestResults({
                type: 'quick',
                score: 0,
                duration: 0,
                status: 'failed',
                error: result.error
            });
        }
        
    } catch (error) {
        addTestLog(`❌ Критическая ошибка: ${error.message}`, 'error');
        updateTestResults({
            type: 'quick',
            score: 0,
            duration: 0,
            status: 'error',
            error: error.message
        });
    } finally {
        currentTest = null;
        updateTestStatus('Тест завершен');
    }
}

// Запуск полного теста
async function runFullTest() {
    if (currentTest) {
        addTestLog('Тест уже запущен', 'warning');
        return;
    }
    
    addTestLog('🔍 Запуск полного теста...', 'info');
    updateTestStatus('Выполняется полный тест...');
    currentTest = 'full';
    
    try {
        const response = await fetch('/api/test/full', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            addTestLog(`✅ Полный тест завершен: ${result.score || 'N/A'}%`, 'success');
            
            // Добавляем дополнительную информацию
            if (result.nodes_started !== undefined) {
                addTestLog(`📊 Узлов запущено: ${result.nodes_started}`, 'info');
            }
            if (result.test_completed !== undefined) {
                addTestLog(`🎯 Тест завершен: ${result.test_completed ? 'Да' : 'Нет'}`, 'info');
            }
            
            updateTestResults({
                type: 'full',
                score: result.score || 0,
                duration: result.duration || 0,
                status: 'completed',
                nodes_started: result.nodes_started,
                test_completed: result.test_completed
            });
        } else {
            addTestLog(`❌ Ошибка полного теста: ${result.error}`, 'error');
            updateTestResults({
                type: 'full',
                score: 0,
                duration: 0,
                status: 'failed',
                error: result.error
            });
        }
        
    } catch (error) {
        addTestLog(`❌ Критическая ошибка: ${error.message}`, 'error');
        updateTestResults({
            type: 'full',
            score: 0,
            duration: 0,
            status: 'error',
            error: error.message
        });
    } finally {
        currentTest = null;
        updateTestStatus('Тест завершен');
    }
}

// Запуск нагрузочного теста
async function runStressTest() {
    if (currentTest) {
        addTestLog('Тест уже запущен', 'warning');
        return;
    }
    
    addTestLog('💪 Запуск нагрузочного теста...', 'info');
    updateTestStatus('Выполняется нагрузочный тест...');
    currentTest = 'stress';
    
    try {
        const response = await fetch('/api/test/stress', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            addTestLog(`✅ Нагрузочный тест завершен: ${result.score || 'N/A'}%`, 'success');
            
            // Добавляем дополнительную информацию
            if (result.nodes_started !== undefined) {
                addTestLog(`📊 Узлов запущено: ${result.nodes_started}`, 'info');
            }
            if (result.test_completed !== undefined) {
                addTestLog(`🎯 Тест завершен: ${result.test_completed ? 'Да' : 'Нет'}`, 'info');
            }
            
            updateTestResults({
                type: 'stress',
                score: result.score || 0,
                duration: result.duration || 0,
                status: 'completed',
                nodes_started: result.nodes_started,
                test_completed: result.test_completed
            });
        } else {
            addTestLog(`❌ Ошибка нагрузочного теста: ${result.error}`, 'error');
            updateTestResults({
                type: 'stress',
                score: 0,
                duration: 0,
                status: 'failed',
                error: result.error
            });
        }
        
    } catch (error) {
        addTestLog(`❌ Критическая ошибка: ${error.message}`, 'error');
        updateTestResults({
            type: 'stress',
            score: 0,
            duration: 0,
            status: 'error',
            error: error.message
        });
    } finally {
        currentTest = null;
        updateTestStatus('Тест завершен');
    }
}

// Запуск всех тестов
async function runAllTests() {
    if (currentTest) {
        addTestLog('Тест уже запущен', 'warning');
        return;
    }
    
    addTestLog('🧪 Запуск всех тестов...', 'info');
    updateTestStatus('Выполняются все тесты...');
    currentTest = 'all';
    
    const tests = [
        { name: 'quick', func: runQuickTest, label: 'Быстрый тест' },
        { name: 'full', func: runFullTest, label: 'Полный тест' },
        { name: 'stress', func: runStressTest, label: 'Нагрузочный тест' }
    ];
    
    const results = [];
    
    for (const test of tests) {
        addTestLog(`Запуск: ${test.label}`, 'info');
        
        try {
            const response = await fetch(`/api/test/${test.name}`, {
                method: 'POST'
            });
            
            const result = await response.json();
            
            if (response.ok) {
                addTestLog(`✅ ${test.label}: ${result.score || 'N/A'}%`, 'success');
                results.push({
                    type: test.name,
                    score: result.score || 0,
                    duration: result.duration || 0,
                    status: 'completed'
                });
            } else {
                addTestLog(`❌ ${test.label}: ${result.error}`, 'error');
                results.push({
                    type: test.name,
                    score: 0,
                    duration: 0,
                    status: 'failed',
                    error: result.error
                });
            }
            
            // Пауза между тестами
            await new Promise(resolve => setTimeout(resolve, 1000));
            
        } catch (error) {
            addTestLog(`❌ ${test.label}: ${error.message}`, 'error');
            results.push({
                type: test.name,
                score: 0,
                duration: 0,
                status: 'error',
                error: error.message
            });
        }
    }
    
    // Подсчет общей оценки
    const totalScore = results.reduce((sum, r) => sum + r.score, 0);
    const averageScore = results.length > 0 ? totalScore / results.length : 0;
    const totalDuration = results.reduce((sum, r) => sum + r.duration, 0);
    
    addTestLog(`🎯 Все тесты завершены. Средняя оценка: ${averageScore.toFixed(1)}%`, 'success');
    addTestLog(`⏱️ Общая длительность: ${totalDuration.toFixed(1)} сек`, 'info');
    
    updateTestResults({
        type: 'all',
        score: averageScore,
        duration: totalDuration,
        status: 'completed',
        details: results
    });
    
    currentTest = null;
    updateTestStatus('Все тесты завершены');
}

// Обновление статуса теста
function updateTestStatus(status) {
    const statusElement = document.getElementById('last-test-status');
    if (statusElement) {
        statusElement.textContent = status;
    }
}

// Обновление результатов тестов
function updateTestResults(result) {
    testResults.unshift(result);
    
    // Ограничиваем историю результатов
    if (testResults.length > 10) {
        testResults = testResults.slice(0, 10);
    }
    
    displayTestResults();
}

// Отображение результатов тестов
function displayTestResults() {
    const resultsContainer = document.getElementById('test-results');
    if (!resultsContainer) return;
    
    if (testResults.length === 0) {
        resultsContainer.innerHTML = `
            <div class="result-card">
                <h4>Последний запуск</h4>
                <p>Тесты не запускались</p>
            </div>
        `;
        return;
    }
    
    const latestResult = testResults[0];
    
    let statusIcon = '⏳';
    let statusClass = '';
    
    if (latestResult.status === 'completed') {
        statusIcon = latestResult.score >= 85 ? '✅' : latestResult.score >= 70 ? '⚠️' : '❌';
        statusClass = latestResult.score >= 85 ? 'success' : latestResult.score >= 70 ? 'warning' : 'error';
    } else if (latestResult.status === 'failed') {
        statusIcon = '❌';
        statusClass = 'error';
    } else if (latestResult.status === 'error') {
        statusIcon = '💥';
        statusClass = 'error';
    }
    
    let detailsHtml = '';
    if (latestResult.details && Array.isArray(latestResult.details)) {
        detailsHtml = latestResult.details.map(detail => 
            `<div class="sub-result">
                <span>${detail.type}:</span>
                <span class="${detail.status}">${detail.score.toFixed(1)}%</span>
            </div>`
        ).join('');
    }
    
    resultsContainer.innerHTML = `
        <div class="result-card ${statusClass}">
            <h4>${statusIcon} Последний запуск</h4>
            <p><strong>Тип:</strong> ${getTestTypeName(latestResult.type)}</p>
            <p><strong>Результат:</strong> ${latestResult.score.toFixed(1)}%</p>
            <p><strong>Длительность:</strong> ${latestResult.duration.toFixed(1)} сек</p>
            <p><strong>Статус:</strong> ${getStatusText(latestResult.status)}</p>
            ${latestResult.error ? `<p class="error"><strong>Ошибка:</strong> ${latestResult.error}</p>` : ''}
            ${detailsHtml ? `<div class="sub-results">${detailsHtml}</div>` : ''}
        </div>
    `;
}

// Получение названия теста
function getTestTypeName(type) {
    const names = {
        'quick': 'Быстрый тест',
        'full': 'Полный тест',
        'stress': 'Нагрузочный тест',
        'all': 'Все тесты'
    };
    return names[type] || type;
}

// Получение текста статуса
function getStatusText(status) {
    const texts = {
        'completed': 'Завершен',
        'failed': 'Провален',
        'error': 'Ошибка',
        'running': 'Выполняется'
    };
    return texts[status] || status;
}

// Добавление записи в лог
function addTestLog(message, type = 'info') {
    const logContent = document.getElementById('test-log-content');
    if (!logContent) return;
    
    const timestamp = new Date().toLocaleTimeString();
    
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.innerHTML = `<span class="timestamp">[${timestamp}]</span> ${message}`;
    
    logContent.insertBefore(entry, logContent.firstChild);
    
    // Ограничить количество записей
    while (logContent.children.length > 100) {
        logContent.removeChild(logContent.lastChild);
    }
}

// Очистка логов
function clearTestLogs() {
    const logContent = document.getElementById('test-log-content');
    if (logContent) {
        logContent.innerHTML = '';
        addTestLog('Логи очищены', 'info');
    }
}

// Инициализация дашборда
function initializeDashboard() {
    displayTestResults();
    addTestLog('Дашборд тестирования загружен', 'success');
    
    // Проверяем доступность тестовых API
    checkTestAPI();
}

// Проверка доступности тестовых API
async function checkTestAPI() {
    try {
        const response = await fetch('/api/test/status');
        if (response.ok) {
            addTestLog('Тестовые API доступны', 'success');
        } else {
            addTestLog('Тестовые API недоступны', 'warning');
        }
    } catch (error) {
        addTestLog('Тестовые API недоступены: ' + error.message, 'warning');
    }
}

// Глобальная функция для очистки логов
function clearLogs() {
    clearTestLogs();
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('test-results')) {
        initializeDashboard();
    }
});
