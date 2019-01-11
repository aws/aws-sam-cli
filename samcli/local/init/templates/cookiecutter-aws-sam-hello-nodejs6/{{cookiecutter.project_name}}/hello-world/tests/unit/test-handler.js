'use strict';

const app = require('../../app.js');
const chai = require('chai');
const expect = chai.expect;
var event, context;

describe('Tests Handler', function () {
    it('verifies successful response', function (done) {
        app.lambdaHandler(event, context, function (err, result) {
            try {
                expect(result).to.be.an('object');
                expect(result.statusCode).to.equal(200);
                expect(result.body).to.be.an('string');

                let response = JSON.parse(result.body);

                expect(response).to.be.an('object');
                expect(response.message).to.be.equal("hello world");
                // expect(response.location).to.be.an("string");
                done();
            } catch (e) {
                done(e);
            }
        });
    });
});
