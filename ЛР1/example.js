function isPrime(num) {
    if (num <= 1) {
        return false;
    }
    for (let i = 2; i <= Math.sqrt(num); i++) {
        if (num % i === 0) {
            return false;
        }
    }
    return true;
}

let count = 0;
let limit = 50;
for (let n = 2; n < limit; n = n + 1) {
    if (isPrime(n)) {
        count = count + 1;
        console.log(n);
    }
}

let ratio = (count / limit) * 100;
