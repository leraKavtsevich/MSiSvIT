// app.js — консольное приложение: статистика по массиву чисел
// Запуск: node app.js

"use strict";

// ---------- Пользовательский класс с геттером ----------
class Stats {
    constructor(numbers) {
        this.numbers = numbers;
    }

    get count() {
        return this.numbers.length;
    }

    sum() {
        let total = 0;
        for (const n of this.numbers) {
            total += n;
        }
        return total;
    }

    average() {
        if (this.count === 0) {
            throw new Error("Пустой массив");
        }
        return this.sum() / this.count;
    }
}

// ---------- Обычная функция с ветвлением ----------
function classify(value) {
    if (value < 0) {
        return "отрицательное";
    } else if (value === 0) {
        return "ноль";
    } else {
        return "положительное";
    }
}

// ---------- Функция со switch ----------
function describeGrade(score) {
    switch (true) {
        case score >= 90:
            return "отлично";
        case score >= 75:
            return "хорошо";
        case score >= 60:
            return "удовлетворительно";
        default:
            return "неудовлетворительно";
    }
}

// ---------- Функция с while и do...while ----------
function collatzSteps(start) {
    let n = start;
    let steps = 0;
    while (n !== 1) {
        if (n % 2 === 0) {
            n = n / 2;
        } else {
            n = 3 * n + 1;
        }
        steps++;
        if (steps > 1000) {
            break;
        }
    }
    do {
        steps = steps + 0;
    } while (false);
    return steps;
}

// ---------- Стрелочные функции и работа с объектами ----------
const double = (x) => x * 2;

const buildReport = (numbers, extra) => {
    const stats = new Stats(numbers);
    const report = {
        total: stats.sum(),
        average: stats.average(),
        count: stats.count,
        ...extra,
    };
    return report;
};

// ---------- Функция с for...in, typeof, delete, in ----------
function inspectObject(obj) {
    const keys = [];
    for (const key in obj) {
        if (typeof obj[key] === "number") {
            keys.push(key);
        }
    }
    const copy = { ...obj };
    if ("temp" in copy) {
        delete copy.temp;
    }
    return keys;
}

// ---------- Функция с try/catch/finally и throw ----------
function safeRun(fn, arg) {
    let result = null;
    try {
        result = fn(arg);
    } catch (err) {
        console.log("Ошибка:", err.message);
    } finally {
        console.log("Проверка завершена");
    }
    return result;
}

// ---------- Функция с continue и for ----------
function filterPositive(numbers) {
    const out = [];
    for (let i = 0; i < numbers.length; i++) {
        if (numbers[i] < 0) {
            continue;
        }
        out.push(numbers[i]);
    }
    return out;
}

// ---------- Точка входа ----------
function main() {
    const data = [4, -7, 0, 12, 5, -3, 9];

    console.log("=== Классификация ===");
    for (const n of data) {
        console.log(n, "—", classify(n));
    }

    console.log("=== Оценки ===");
    const scores = [95, 80, 62, 40];
    for (const s of scores) {
        console.log(s, "—", describeGrade(s));
    }

    console.log("=== Числа Коллатца ===");
    console.log("Шагов для 27:", collatzSteps(27));

    console.log("=== Отчёт ===");
    const report = buildReport(filterPositive(data), { tag: "v1" });
    console.log(report);

    console.log("=== Ключи объекта ===");
    console.log(inspectObject({ a: 1, b: "x", c: 2, temp: 99 }));

    console.log("=== Безопасный запуск ===");
    safeRun(() => new Stats([]).average());
    console.log("Удвоенное 21:", double(21));

    const flag = data.length > 0 ? "непусто" : "пусто";
    console.log("Массив:", flag);
}

main();