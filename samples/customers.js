'use strict';

exports.handler = (event, context, callback) => {

    
    switch (event.httpMethod) {
        case 'GET':
            let id = event.pathParameters.customer;
            callback(null, id ? getCustomer(id) : getCustomers());

        default:
            // Send HTTP 501: Not Implemented
            callback(null, { statusCode: 501 })
    }

}

function getCustomers() {
    return [
        { id: 1, name: "Paul Maddox", alias: "pmaddox" },
        { id: 2, name: "Jack Bobby", alias: "jbob" },
        { id: 3, name: "Alice Townton", alias: "atownton" }
    ];
}

function getCustomer(id) {

    for(let customer of getCustomers()){
        if(customer.id == id){
            return customer;
        }
     }

    // No customer exists with the provided ID
    return { statusCode: 404 };

}