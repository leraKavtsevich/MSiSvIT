// Обработка результатов сессии группы студентов

const students = [
    { name: "Иванов", marks: { math: 9, physics: 7, history: 4 } },
    { name: "Петров", marks: { math: 3, physics: 2, history: 4 } },
    { name: "Сидорова", marks: { math: 10, physics: 9, history: 8 } },
];

function average(marks) {
    let sum = 0;
    let count = 0;
    for (const subject in marks) {
        sum += marks[subject];
        count++;
    }
    return count > 0 ? sum / count : 0;
}

function grade(avg) {
    let level = Math.floor(avg);
    let result;
    switch (level) {
        case 10:
        case 9:
            result = "отлично";
            break;
        case 8:
        case 7:
            result = "хорошо";
            break;
        case 6:
        case 5:
        case 4:
            result = "удовлетворительно";
            break;
        default:
            result = "неудовлетворительно";
    }
    return result;
}

let debtors = 0;
for (const student of students) {
    const avg = average(student.marks);
    if (avg >= 4) {
        console.log(student.name + ": " + grade(avg));
    } else {
        debtors++;
        for (let attempt = 1; attempt <= 3; attempt++) {
            if (attempt === 3) {
                console.log(student.name + ": комиссия");
            } else if (attempt === 1) {
                console.log(student.name + ": пересдача");
            }
        }
    }
}

let i = 0;
while (i < students.length && students[i].marks.math < 10) {
    i++;
}

let attempts = 0;
do {
    attempts++;
} while (attempts < debtors);

async function printNames() {
    for await (const s of students) {
        console.log(s.name);
    }
}
printNames();
