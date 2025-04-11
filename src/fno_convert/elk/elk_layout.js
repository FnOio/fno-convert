import ELK from "elkjs"

const elk = new ELK();

// Read JSON from stdin
let inputData = "";

process.stdin.on("data", (chunk) => {
    inputData += chunk;
});

process.stdin.on("end", async () => {
    try {
        const jsonData = JSON.parse(inputData);

        // Compute layout
        const layout = await elk.layout(jsonData);

        // Output the modified ELK JSON
        console.log(JSON.stringify(layout));
    } catch (error) {
        console.error("Error processing ELK JSON:", error);
    }
});
