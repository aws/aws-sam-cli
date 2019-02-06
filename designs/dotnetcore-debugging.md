# .NET Core 2.0 / 2.1 Debugging

This is a design for the .NET Core 2.0 and 2.1 missing debugging feature.

### What is the problem

Currently SAM CLI does not provide debugging support for .NET Core 2.0 and 2.1 because `dotnet` command does **not** support _start and wait for the debugger_ configuration out of the box and neither does current AWS Lambda runner ([2.0](https://github.com/lambci/docker-lambda/tree/master/dotnetcore2.0) / [2.1](https://github.com/lambci/docker-lambda/tree/master/dotnetcore2.1)) has debugging support flag or anything.

Apart from that, .NET Core remote debugger - [vsdbg](https://aka.ms/getvsdbgsh) does not support http based communication, but instead only piping `stdin/stdout` through some transport program from host to the **target** machine (Docker container) could enable debugging. For that C# VS Code *extension* [has support](https://github.com/OmniSharp/omnisharp-vscode/wiki/Attaching-to-remote-processes) for configuring `pipeTransport`. Customers could use this mechanism to remotely attach to the running Lambda container with their function. Our goal is to provide  `launch.json` configuration capable of doing so to the users, and enable debugging support on the **runner side**.

And let's break it down to the checklist

* Get and build `vsdbg` for the Lambda container.
* Mount `vsdbg` to the running Docker container.
* Add _"wait for the debugger"_ flag to the runner program and implement corresponding functionality.
* Implement corresponding container entry point override in SAM CLI to support invoking the runner with this flag **on**.
* Provide instructions for the customer of how to configure VS Code and VS to attach.

### What will be changed

Runner program for .NET core [2.0](https://github.com/lambci/docker-lambda/blob/master/dotnetcore2.0/run/MockBootstraps/Program.cs) and [2.1](https://github.com/lambci/docker-lambda/blob/master/dotnetcore2.1/run/MockBootstraps/Program.cs) in another [repo](https://github.com/lambci/docker-lambda) to support *waiting for the debugger* to attach. I've filed [PR](https://github.com/lambci/docker-lambda/pull/130) with only required changes already (✅ merged);

The good part is that no new commands or parameters on SAM CLI side are required.

### Success Criteria

1. Provide handy script to get the `vsdbg` via downloading it to the .NET Lambda runtime container, installing it and getting through the mounting (or manual instructions to achieve the above results). After that user would be able to provide it to SAM CLI via `--debugger-path`.
2. Provide ready-to-go `launch.json` configuration for attaching to the Lambda function via VS Code.
3. Customer should be able to easily debug .NET Core 2.0 and 2.1 apps on VS Code (minimal requirement).

### Out-of-Scope

SAM CLI users can perform debugging via Visual Studio 2017 also, but it has some other very different Docker container debugging support, and to keep things consistent it requires over complicated setup from the user. More about approach [here](https://github.com/Microsoft/MIEngine/wiki/Offroad-Debugging-of-.NET-Core-on-Linux---OSX-from-Visual-Studio). So we've decided that it would be a better long term solution to hand this are over to the [new AWS Lambda Test Tool](https://github.com/aws/aws-lambda-dotnet/tree/master/Tools/LambdaTestTool) of VS 2017 AWS Toolkit.

Rider support needs separate investigation, as it does not support `vsdbg` by any means (licensing [issue](https://github.com/dotnet/core/issues/505)) and therefore they have [their own](https://blog.jetbrains.com/dotnet/2017/02/23/rider-eap-18-coreclr-debugging-back-windows/) debugger implementation and possibly UX around .NET Core remote debugging. If support is required - I think we should open another issue. 

### User Experience Walkthrough

##### 1. Getting the debugger locally

At first, user should be able to get and install `vsdbg` on their machine easily. For this we should provide instruction (like it was done for `golang` debugger installation) for them to follow, which will effectively spin up .NET Lambda runtime Docker container with mounted via `bind` path to get the debugger on the **host** machine.

In this container following: `curl -sSL https://aka.ms/getvsdbgsh | bash /dev/stdin -v latest -l /vsdbg` should be run to get and install required debugger (specifically built for this container). Later SAM will mount this same folder with the debugger to the target running container. 

Commands below (compatible with `powershell` and `bash`) are taken from my prepared [POC](https://github.com/ndobryanskyy/dotnetcore-aws-local-debugging-poc) and meet all of the above requirements:

```sh
# Create directory to store debugger locally
mkdir $HOME/vsdbg

# Mount this to get built vsdbg for AWS Lambda runtime container on host machine
docker run --rm --mount type=bind,src=$HOME/vsdbg,dst=/vsdbg --entrypoint bash lambci/lambda:dotnetcore2.0 -c "curl -sSL https://aka.ms/getvsdbgsh | bash /dev/stdin -v latest -l /vsdbg"
```

*Note: we are building on* `:dotnetcore2.0` *just to ensure the support of minimal version. As for now, it makes no difference which image to choose.*

##### 2. Publishing the code

Customer should be informed, that in order to have the best debugging experience app must be published in `Debug` configuration by supplying `-c Debug` flag for `dotnet publish` command. 

_For example:_

```sh
dotnet publish -c Debug -o out

# Or via container
docker run --rm --mount src=$(PWD),dst=/var/task,type=bind lambci/lambda:build-dotnetcore2.1 dotnet publish -c Debug -o out
```

##### 3. Attaching

Customer will use ready-to-go `launch.json` (example could be found [here](https://github.com/ndobryanskyy/dotnetcore-aws-local-debugging-poc/blob/master/Lambda/.vscode/launch.json)) debug configuration for VS Code, fill in `debugger_port` for the `docker ps` and supply this port to SAM CLI while invoking.

_For example:_

```sh
sam local invoke --event event.json -d 6000 --debugger-path ~/vsdbg
```

After invoking the function in command line, customer will see:

```
Waiting for the debugger to attach...
```

After that user should just conveniently click the _start debugging_ button with our **".NET Core Docker Attach"** configuration. 

## Implementation

### CLI Changes

None required. We would happily use `debugger_port` and `debugger_path` like other runtimes.

### Design 

##### Supplying debugger

We will have pretty similar approach to what GO is now doing. Customer will get the `vsdbg` on their machine and supply it to SAM via `--debugger-path` . So everything for the first step is already implemented and we will reuse that mechanism.

##### Runner with debugging support

As for the debugging support for the runner, unfortunately `dotnet` command does not support _"start and wait"_ configuration out of the box. Neither does C# provide any event which notifies, that debugger was attached. Therefore we will implement custom mechanism for that. 

During the discussion in this related [issue](https://github.com/awslabs/aws-sam-cli/issues/568) it was decided to go with infinite loop approach. It means that program will query [Debugger.IsAttached](https://docs.microsoft.com/en-us/dotnet/api/system.diagnostics.debugger.isattached?view=netcore-2.0) property with some interval (for now it is 50ms - which seems instantaneous for the user), also we have timeout for this loop which is 10 minutes for now (thanks for shaping that out, @mikemorain, @sanathkr). Interval and timeout are **open** for suggestions and edits.

_Examine the code from [PR](https://github.com/lambci/docker-lambda/pull/130/files):_

```c#
public static bool TryWaitForAttaching(TimeSpan queryInterval, TimeSpan timeout)
{
	var stopwatch = Stopwatch.StartNew();
  
  while (!Debugger.IsAttached)
  {
  	if (stopwatch.Elapsed > timeout)
    {
    	return false;
    }
    
    Task.Delay(queryInterval).Wait();
  }
  
  return true;
}
```

Also for this program `-d` flag was added which, when specified, will make the runner wait for the debugger to attach.

##### Attaching

Now, as our runner supports waiting for the debugger to attach, the only thing left to do is actually attach to the `dotnet` process with our Lambda **inside** the Docker container. For that I suggest using remote `dotnet` [debugging support](https://github.com/OmniSharp/omnisharp-vscode/wiki/Attaching-to-remote-processes) from VS Code C# extension. We will take advantage of its `pipeTransport` feature. 

`docker exec` is used to step into the running container and serve as a `pipeTransport` to perform .NET Core remote debugging and one very neat trick with `docker ps` [command](https://docs.docker.com/engine/reference/commandline/ps/) to avoid introducing any changes to SAM CLI and provide user unified UX across runtimes. 

SAM CLI internally uses *published port* to provide debugging support for all of its runtimes. But .NET Core debugger is not capable of running in http mode. That is why VS Code C# extension provides `pipeTransport` configuration section to enable remote .NET debugging. User must provide `pipeProgram` which will let VS Code to talk to `vsdbg` located under `debuggerPath` on **target** machine (Docker container in our case).

I've chosen `docker` to serve as `pipeProgram` via its `exec` command. By supplying `-i` flag we keep the `stdin` open to let VS Code perform its communication via `stdin/stdout`. The only unsolved part in this equation is how do we know `container name` or `container id` to perform `exec` on, because SAM CLI does not specifically set those. And the answer is - use `docker ps` with filter! 🎉

```
docker ps -q -f publish=<debugger_port>
```

`-q` will make this command print only the id of the container, and `-f publish=<port>` will filter containers based on the published port, pretty neat, right? This exact trick was used in [launch.json](https://github.com/ndobryanskyy/dotnetcore-aws-local-debugging-poc/blob/master/Lambda/.vscode/launch.json) from POC to get container id for the `docker exec` command. I've used `powershell` on windows to get this nested command working (but the sample includes configuration for OSX and Linux also).

_Examine sample launch.json configuration_

```
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": ".NET Core Docker Attach",
      "type": "coreclr",
      "request": "attach",
      "processId": "1",

      "pipeTransport": {
        "pipeProgram": "sh",
        "pipeArgs": [ 
          "-c",
          "docker exec -i $(docker ps -q -f publish=<debugger_port>) ${debuggerCommand}"
        ],
        "debuggerPath": "/vsdbg/vsdbg",
        "pipeCwd": "${workspaceFolder}",
      },

      "windows": {
        "pipeTransport": {
          "pipeProgram": "powershell",
          "pipeArgs": [ 
            "-c",
            "docker exec -i $(docker ps -q -f publish=<debugger_port>) ${debuggerCommand}"
          ],
          "debuggerPath": "/vsdbg/vsdbg",
          "pipeCwd": "${workspaceFolder}",
        }
      },

      "sourceFileMap": {
        "/var/task": "${workspaceFolder}"
      }
    }
  ]
}
```

As for the `processId` - luckily entry point program always gets PID of 1 in a running container, so no remote picker required!

### Open questions

1. A bit off-topic, but still, has someone else encountered the problem with python 3.7.1 ? As it now does not flush the `stdout` and `stderr` from the running container immediately but rather after SAM ends the invocation, and user does not see _"waiting for the debugger to attach..."_ message. Which leads to bad debugging experience. this behavior is also reproduced on any python (except 2.7). And I see some correlation with this [issue](https://github.com/awslabs/aws-sam-cli/pull/729). I've tested and the problem is certainly on Python side, as auto flushing is enabled in .NET by default;

   **UPD**: Filed [PR](https://github.com/awslabs/aws-sam-cli/pull/843) that fixes that.

2. Jet Brains Rider support remains under question too;

3. VS Code .NET debugger adapter from C# extension `vsdbg-ui` reports _"The pipe program 'docker' exited unexpectedly with code 137."_ after debugger session ends. It seems, that 137 (*128+9*) is **killed** exit code, which seems a bit strange. I could not track the issue to the core because `vsdbg` is not open source actually.

   I've investigated this issue and it turned out, that this behavior is observed (on my Windows machine) for any remote .NET debugging inside Docker container. I will reach out to `csharp` extension team to get their thoughts on that.

   **UPD**: Just the same behavior is observed on Mac machine.



### Tasks breakdown

- [x] Submit PR with the design doc;
- [x] Submit PR with runner program improvements;
- [x] Submit PR with changes and user documentation required to take advantage of .NET Core debugging to SAM CLI repo.
- [x] Merge [PR](https://github.com/lambci/docker-lambda/pull/130) to `lambci/docker-lambda` [repo](https://github.com/lambci/docker-lambda);
- [x] Investigate debugging support for VS 2017