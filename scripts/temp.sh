#!/bin/bash

# Função para ler temperatura de forma robusta
read_temperature() {
    local sensor_path="/sys/class/thermal/thermal_zone0/temp"
    local temp=""
    local result=""

    if [[ -f "$sensor_path" ]]; then
        temp=$(cat "$sensor_path" 2>/dev/null)
        if [[ $? -eq 0 && "$temp" =~ ^[0-9]+$ ]]; then
            # Converte para float em graus Celsius
            result=$(echo "scale=1; $temp/1000" | bc)
            if [[ "$result" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
                echo "$result"
                return 0
            else
                echo "Erro: Valor inválido convertido."
                return 4
            fi
        else
            echo "Erro: Falha ao ler o valor do sensor."
            return 2
        fi
    else
        # Tenta usar o comando sensors se disponível
        if command -v sensors >/dev/null 2>&1; then
            temp=$(sensors | grep -m1 -E 'temp[0-9]+:' | awk '{print $2}' | tr -d '+°C')
            if [[ "$temp" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
                echo "$temp"
                return 0
            else
                echo "Erro: Não foi possível obter a temperatura via sensors."
                return 3
            fi
        else
            echo "Erro: Nenhum método disponível para leitura de temperatura."
            return 1
        fi
    fi
}

# Exemplo de uso
read_temperature
