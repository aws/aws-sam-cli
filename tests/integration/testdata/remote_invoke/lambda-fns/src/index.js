exports.handler = awslambda.streamifyResponse(
    async (event, responseStream, context) => {
        responseStream.write("Lambda");
        responseStream.write("Function");

        responseStream.write("Streaming");
        await new Promise(r => setTimeout(r, 1000));
        responseStream.write("Responses");
        await new Promise(r => setTimeout(r, 1000));
        responseStream.write("Test");
        await new Promise(r => setTimeout(r, 1000));

        responseStream.write("Done!");
        responseStream.end();
    }
);

exports.stream_event_values = awslambda.streamifyResponse(
    async (event, responseStream, context) => {
        for (let k in event) {
            responseStream.write(event[k]);
            await new Promise(r => setTimeout(r, 1000));
          }
        responseStream.end();
    }
);