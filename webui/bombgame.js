(function () {
    const UI_VERSION = "0.1-a1"
    const WS_PORT = 8081
    const WS_PATH = "/ws"

    const MODULE_NAMES = {
        1: "Timer",
        2: "Wires",
        4: "Keypad",
        5: "Simon Says"
    }

    const ERROR_LEVELS = ["NONE", "INFO", "RECOVERED", "WARNING", "RECOVERABLE", "MINOR", "MAJOR", "INIT_FAILURE", "FATAL"]

    let connected = false

    const log = msg => {
        const area = document.getElementById("errorLog")
        area.textContent = `${msg}\n${area.textContent}`
    }

    const range = to => [...Array(to).keys()]

    const moduleElems = range(12).map(index => document.getElementById(`module${index}`))
    const modules = Array(12).fill(null)

    const assert = assertion => {
        if (!assertion) log(`Assertion failed!\n${new Error().stack}`)
    }

    const makeNonpresentModuleElem = elem => {
        elem.className = "module"
        elem.innerHTML = `
        <div class="errorIndicator"></div>
        `
    }

    const makePresentModuleElem = elem => {
        elem.className = "module present"
        elem.innerHTML = `
            <div class="statusLed"></div>
            <div class="errorIndicator"></div>
            <h4 class="moduleName"></h4>
            <div class="details"></div>
        `
    }

    const updateModuleElem = (module, elem) => {
        elem.className = "module present"
        elem.classList.add("state_" + module.state.toLowerCase())
        elem.classList.add("errorLevel_" + module.error_level.toLowerCase())
        elem.querySelector(".moduleName").textContent = module.module_name
        elem.querySelector(".details").textContent = `Serial: ${module.serial}\nState: ${module.state}`
    }

    const ws = new WebSocket(`ws://${location.hostname}:${WS_PORT}${WS_PATH}`)
    ws.addEventListener("close", e => {
        switch (e.code) {
        case 4000:
            log(`[INFO] Disconnected because another client connected`)
            break
        case 4001:
            log(`[ERROR] UI version mismatch, please refresh the page`)
            break
        case 4002:
            log(`[ERROR] The server requires a password, which is not supported yet`)
            break
        case 4003:
            log(`[ERROR] The entered password was incorrect`)
            break
        case 1001:
            log(`[INFO] The server is shutting down`)
            break
        case 1005:
        case 1006:
            if (connected) {
                log(`[ERROR] WebSocket closed abnormally`)
            } else {
                log(`[ERROR] WebSocket failed to connect`)
            }
            break
        default:
            log(`[ERROR] WebSocket closed with code ${e.code}: ${e.reason}`)
            break
        }
        connected = false
    })
    ws.addEventListener("message", e => {
        let data
        try {
            data = JSON.parse(e.data)
        } catch (_) {
            log("[ERROR] Invalid data received from WebSocket")
            return
        }
        switch (data.type) {
        case "reset":
            for (let i = 0; i < 12; i++) {
                modules[i] = null
            }
            moduleElems.forEach(makeNonpresentModuleElem)
            break
        case "add_module":
            assert(modules[data.location] === null)
            modules[data.location] = {
                module_type: data.module_type,
                module_name: MODULE_NAMES[data.module_type],
                serial: data.serial,
                state: data.state,
                error_level: data.error_level,
                details: data.details
            }
            makePresentModuleElem(moduleElems[data.location])
            updateModuleElem(modules[data.location], moduleElems[data.location])
            break
        case "update_module":
            assert(modules[data.location] !== null)
            modules[data.location] = {
                ...modules[data.location],
                state: data.state,
                details: data.details
            }
            updateModuleElem(modules[data.location], moduleElems[data.location])
            break
        case "error":
            if (data.module !== null && modules[data.module] !== null) {
                const module = modules[data.module]
                log(`[${data.level}] ${module.module_name} @ ${data.module}: ${data.message}`)
                module.error_level = ERROR_LEVELS[Math.max(ERROR_LEVELS.indexOf(module.error_level), ERROR_LEVELS.indexOf(data.level))]
                updateModuleElem(module, moduleElems[data.module])
            } else {
                log(`[${data.level}] ${data.message}`)
            }
            break
        default:
            log(`[MSG] ${e.data}`)
            break
        }
    })
    ws.addEventListener("open", e => {
        connected = true
        ws.send(JSON.stringify({
            "type": "login",
            "ui_version": UI_VERSION,
            "password": null
        }))
    })

    document.getElementById("reset").addEventListener("click", e => {
        if (!connected) return
        ws.send(JSON.stringify({
            "type": "reset"
        }))
    })
    document.getElementById("startGame").addEventListener("click", e => {
        if (!connected) return
        ws.send(JSON.stringify({
            "type": "start_game"
        }))
    })
})()